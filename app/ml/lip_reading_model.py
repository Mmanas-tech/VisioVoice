"""3D CNN Lip-Reading Model with ResNet3D-34 backbone and Temporal Attention."""

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class Conv3DBlock(nn.Module):
    """3D convolution block with BatchNorm and ReLU."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: Tuple[int, int, int] = (3, 3, 3),
        stride: Tuple[int, int, int] = (1, 1, 1),
        padding: Tuple[int, int, int] = (1, 1, 1),
        use_pool: bool = False,
    ):
        super().__init__()
        self.conv = nn.Conv3d(in_channels, out_channels, kernel_size, stride, padding, bias=False)
        self.bn = nn.BatchNorm3d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.pool = nn.MaxPool3d((1, 2, 2)) if use_pool else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu(self.bn(self.conv(x)))
        if self.pool:
            x = self.pool(x)
        return x


class ResBlock3D(nn.Module):
    """3D Residual block with skip connection."""

    def __init__(self, in_channels: int, out_channels: int, stride: Tuple[int, int, int] = (1, 1, 1)):
        super().__init__()
        self.conv1 = nn.Conv3d(in_channels, out_channels, (3, 3, 3), stride, (1, 1, 1), bias=False)
        self.bn1 = nn.BatchNorm3d(out_channels)
        self.conv2 = nn.Conv3d(out_channels, out_channels, (3, 3, 3), (1, 1, 1), (1, 1, 1), bias=False)
        self.bn2 = nn.BatchNorm3d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        self.shortcut = nn.Sequential()
        if stride != (1, 1, 1) or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv3d(in_channels, out_channels, (1, 1, 1), stride, bias=False),
                nn.BatchNorm3d(out_channels),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.shortcut(x)
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += residual
        return self.relu(out)


class ResNet3D34(nn.Module):
    """
    3D ResNet-34 backbone for spatiotemporal feature extraction.

    Input: (B, C, T, H, W)
    Output: (B, 512, T', 7, 7)
    """

    def __init__(self, pretrained: bool = False):
        super().__init__()

        self.stem = nn.Sequential(
            Conv3DBlock(3, 64, (3, 7, 7), (1, 2, 2), (1, 3, 3)),
            nn.MaxPool3d((1, 3, 3), (1, 2, 2), (0, 1, 1)),
        )

        self.layer1 = self._make_layer(64, 64, 3, stride=(1, 1, 1))
        self.layer2 = self._make_layer(64, 128, 4, stride=(1, 2, 2))
        self.layer3 = self._make_layer(128, 256, 6, stride=(1, 2, 2))
        self.layer4 = self._make_layer(256, 512, 3, stride=(1, 2, 2))

        self._init_weights()

    def _make_layer(
        self, in_channels: int, out_channels: int, blocks: int, stride: Tuple[int, int, int]
    ) -> nn.Sequential:
        layers = [ResBlock3D(in_channels, out_channels, stride)]
        for _ in range(1, blocks):
            layers.append(ResBlock3D(out_channels, out_channels))
        return nn.Sequential(*layers)

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(m, nn.BatchNorm3d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        return x


class TemporalConv(nn.Module):
    """Temporal convolution for sequence modeling."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        padding = kernel_size // 2
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size, padding=padding)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size, padding=padding)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu(self.bn1(self.conv1(x)))
        x = self.dropout(x)
        x = self.relu(self.bn2(self.conv2(x)))
        return x


class MultiHeadSelfAttention(nn.Module):
    """Multi-head self-attention for temporal modeling."""

    def __init__(self, embed_dim: int, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.num_heads = num_heads
        self.embed_dim = embed_dim
        self.head_dim = embed_dim // num_heads
        assert embed_dim % num_heads == 0

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.head_dim)

    def forward(
        self, x: torch.Tensor, mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, C = x.shape

        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)

        attn_weights = torch.matmul(q, k.transpose(-2, -1)) / self.scale

        if mask is not None:
            attn_weights = attn_weights.masked_fill(mask == 0, float("-inf"))

        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_output = torch.matmul(attn_weights, v)
        attn_output = attn_output.transpose(1, 2).contiguous().view(B, T, C)
        output = self.out_proj(attn_output)

        return output, attn_weights


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for sequence data."""

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


class LipReadingModel(nn.Module):
    """
    Complete Lip-Reading Model.

    Architecture:
    1. ResNet3D-34 3D CNN backbone for spatiotemporal feature extraction
    2. Temporal convolution for sequence modeling
    3. Multi-head self-attention for long-range dependencies
    4. BiGRU decoder for sequence prediction
    5. CTC output head for character prediction

    Input: (B, T, H, W, C) - frames in sequence
    Output: (B, seq_len, vocab_size) - logits per frame
    """

    def __init__(
        self,
        vocab_size: int = 42,
        pretrained_backbone: bool = False,
        attention_heads: int = 4,
        attention_dim: int = 128,
        decoder_hidden: int = 256,
        decoder_layers: int = 2,
        decoder_dropout: float = 0.3,
        bidirectional: bool = True,
    ):
        super().__init__()
        self.vocab_size = vocab_size

        self.encoder = ResNet3D34(pretrained=pretrained_backbone)

        encoder_out_channels = 512

        self.temporal_conv = nn.Sequential(
            TemporalConv(encoder_out_channels, 256, kernel_size=3),
            TemporalConv(256, attention_dim, kernel_size=3),
        )

        self.pos_encoding = PositionalEncoding(attention_dim, dropout=0.1)

        self.self_attention = MultiHeadSelfAttention(
            embed_dim=attention_dim, num_heads=attention_heads, dropout=0.1
        )
        self.attn_norm = nn.LayerNorm(attention_dim)

        self.gru = nn.GRU(
            input_size=attention_dim,
            hidden_size=decoder_hidden,
            num_layers=decoder_layers,
            batch_first=True,
            dropout=decoder_dropout if decoder_layers > 1 else 0,
            bidirectional=bidirectional,
        )

        gru_out_dim = decoder_hidden * 2 if bidirectional else decoder_hidden
        self.fc_out = nn.Sequential(
            nn.Linear(gru_out_dim, gru_out_dim // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(decoder_dropout),
            nn.Linear(gru_out_dim // 2, vocab_size),
        )

        self._init_decoder_weights()

    def _init_decoder_weights(self):
        for name, param in self.gru.named_parameters():
            if "weight" in name:
                nn.init.orthogonal_(param)
            elif "bias" in name:
                nn.init.zeros_(param)
        for module in self.fc_out:
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)

    def forward(
        self, x: torch.Tensor, return_attention: bool = False
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass.

        Args:
            x: Input tensor (B, T, H, W, C) or (B, C, T, H, W)
            return_attention: Also return attention weights

        Returns:
            logits: (B, T', vocab_size)
            attention_weights: Optional (B, heads, T', T')
        """
        if x.dim() == 5 and x.shape[-1] in (1, 3):
            x = x.permute(0, 4, 1, 2, 3)

        features = self.encoder(x)

        features = F.adaptive_avg_pool3d(features, (features.size(2), 1, 1))
        features = features.squeeze(-1).squeeze(-1)

        temporal_feat = self.temporal_conv(features)
        temporal_feat = temporal_feat.permute(0, 2, 1)

        temporal_feat = self.pos_encoding(temporal_feat)

        attn_out, attn_weights = self.self_attention(temporal_feat)
        temporal_feat = self.attn_norm(temporal_feat + attn_out)

        gru_out, _ = self.gru(temporal_feat)

        logits = self.fc_out(gru_out)

        if return_attention:
            return logits, attn_weights
        return logits, None

    def compute_ctc_loss(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        input_lengths: torch.Tensor,
        target_lengths: torch.Tensor,
        blank_index: int = 0,
    ) -> torch.Tensor:
        """Compute CTC loss."""
        log_probs = F.log_softmax(logits, dim=-1)
        log_probs = log_probs.transpose(0, 1)

        loss = F.ctc_loss(
            log_probs, targets, input_lengths, target_lengths,
            blank=blank_index, zero_infinity=True,
        )
        return loss

    def load_checkpoint(self, checkpoint_path: str, strict: bool = False):
        """Load model weights from checkpoint."""
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        else:
            state_dict = checkpoint
        self.load_state_dict(state_dict, strict=strict)

    def count_parameters(self) -> int:
        """Count total trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def create_model(
    vocab_size: int = 42,
    pretrained: bool = False,
    device: str = "cpu",
    checkpoint_path: Optional[str] = None,
) -> LipReadingModel:
    """Factory function to create and optionally load a LipReadingModel."""
    model = LipReadingModel(vocab_size=vocab_size, pretrained_backbone=pretrained)
    if checkpoint_path:
        model.load_checkpoint(checkpoint_path)
    model = model.to(device)
    return model
