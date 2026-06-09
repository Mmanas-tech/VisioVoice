"""Lip-reading neural network model definition."""

import torch
import torch.nn as nn
import torch.nn.functional as F


class LipReadingNetwork(nn.Module):
    """
    Lip-reading network combining CNN feature extraction with Transformer temporal modeling.
    
    Architecture:
    1. CNN backbone for spatial feature extraction from mouth region frames
    2. Transformer encoder for temporal sequence modeling
    3. Classification head for character/token prediction
    """

    def __init__(self, num_classes: int = 500, hidden_dim: int = 256, num_heads: int = 8, num_layers: int = 4):
        super().__init__()
        
        self.cnn_backbone = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            
            nn.Conv2d(256, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((7, 7)),
        )
        
        self.spatial_dim = hidden_dim * 7 * 7
        
        self.projection = nn.Linear(self.spatial_dim, hidden_dim)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=0.1,
            batch_first=True,
        )
        self.temporal_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, num_classes),
        )
        
        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch, time, channels, height, width)
            
        Returns:
            Logits of shape (batch * time, num_classes)
        """
        batch_size, time_steps = x.shape[:2]
        
        x = x.view(batch_size * time_steps, *x.shape[2:])
        
        features = self.cnn_backbone(x)
        features = features.view(batch_size * time_steps, -1)
        features = self.projection(features)
        
        features = features.view(batch_size, time_steps, -1)
        
        temporal_features = self.temporal_encoder(features)
        
        temporal_features = temporal_features.reshape(batch_size * time_steps, -1)
        
        logits = self.classifier(temporal_features)
        
        return logits
