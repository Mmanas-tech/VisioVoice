"""Reference training script for the lip-reading model."""

import argparse
import logging
import os
import time
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torch.cuda.amp import GradScaler, autocast

from app.ml.lip_reading_model import LipReadingModel
from app.ml.vocab import CharacterVocab
from app.ml.preprocessing_config import ModelConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LipReadingDataset(Dataset):
    """Dataset for lip-reading training."""

    def __init__(self, data_dir: str, vocab: CharacterVocab, max_frames: int = 75):
        self.data_dir = data_dir
        self.vocab = vocab
        self.max_frames = max_frames
        self.samples = self._load_samples()

    def _load_samples(self):
        samples = []
        if os.path.exists(self.data_dir):
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".npy"):
                    samples.append(os.path.join(self.data_dir, filename))
        return samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample_path = self.samples[idx]
        data = np.load(sample_path, allow_pickle=True).item()

        frames = data.get("frames", np.zeros((self.max_frames, 224, 224, 3)))
        transcript = data.get("transcript", "")

        if len(frames) > self.max_frames:
            indices = np.linspace(0, len(frames) - 1, self.max_frames, dtype=int)
            frames = frames[indices]
        elif len(frames) < self.max_frames:
            padding = np.zeros((self.max_frames - len(frames), 224, 224, 3))
            frames = np.concatenate([frames, padding], axis=0)

        frames = frames.astype(np.float32) / 255.0
        labels = self.vocab.encode(transcript)

        return (
            torch.from_numpy(frames),
            torch.tensor(labels, dtype=torch.long),
            len(labels),
        )


def collate_fn(batch):
    """Custom collate function with padding."""
    frames, labels, label_lengths = zip(*batch)
    frames = torch.stack(frames)
    labels = nn.utils.rnn.pad_sequence(labels, batch_first=True, padding_value=0)
    label_lengths = torch.tensor(label_lengths, dtype=torch.long)
    return frames, labels, label_lengths


class LipReadingTrainer:
    """Training loop for lip-reading model."""

    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.vocab = CharacterVocab()

        self.model = LipReadingModel(
            vocab_size=self.vocab.size,
            pretrained_backbone=self.config.PRETRAINED_BACKBONE,
            attention_heads=self.config.ATTENTION_HEADS,
            attention_dim=self.config.ATTENTION_DIM,
            decoder_hidden=self.config.DECODER_HIDDEN,
            decoder_layers=self.config.DECODER_LAYERS,
            decoder_dropout=self.config.DECODER_DROPOUT,
        ).to(self.device)

        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.LEARNING_RATE,
            weight_decay=self.config.WEIGHT_DECAY,
        )

        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5
        )

        self.criterion = nn.CTCLoss(blank=self.vocab.blank_index, zero_infinity=True)

        self.scaler = GradScaler() if self.device.type == "cuda" else None

        self.best_val_loss = float("inf")
        self.patience_counter = 0

        logger.info(
            f"Trainer initialized: device={self.device} | "
            f"params={self.model.count_parameters():,} | "
            f"vocab_size={self.vocab.size}"
        )

    def train_epoch(self, dataloader: DataLoader) -> float:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        num_batches = 0

        for batch_idx, (frames, labels, label_lengths) in enumerate(dataloader):
            frames = frames.to(self.device)
            labels = labels.to(self.device)
            label_lengths = label_lengths.to(self.device)

            self.optimizer.zero_grad()

            if self.scaler:
                with autocast():
                    logits, _ = self.model(frames)
                    log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
                    log_probs = log_probs.transpose(0, 1)
                    input_lengths = torch.full((frames.size(0),), logits.size(1), dtype=torch.long)
                    loss = self.criterion(log_probs, labels, input_lengths, label_lengths)

                self.scaler.scale(loss).backward()
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.GRAD_CLIP_NORM)
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                logits, _ = self.model(frames)
                log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
                log_probs = log_probs.transpose(0, 1)
                input_lengths = torch.full((frames.size(0),), logits.size(1), dtype=torch.long)
                loss = self.criterion(log_probs, labels, input_lengths, label_lengths)

                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.GRAD_CLIP_NORM)
                self.optimizer.step()

            total_loss += loss.item()
            num_batches += 1

            if batch_idx % 100 == 0:
                logger.info(f"  Batch {batch_idx}: loss={loss.item():.4f}")

        return total_loss / max(num_batches, 1)

    @torch.no_grad()
    def validate(self, dataloader: DataLoader) -> float:
        """Validate the model."""
        self.model.eval()
        total_loss = 0.0
        num_batches = 0

        for frames, labels, label_lengths in dataloader:
            frames = frames.to(self.device)
            labels = labels.to(self.device)
            label_lengths = label_lengths.to(self.device)

            logits, _ = self.model(frames)
            log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
            log_probs = log_probs.transpose(0, 1)
            input_lengths = torch.full((frames.size(0),), logits.size(1), dtype=torch.long)
            loss = self.criterion(log_probs, labels, input_lengths, label_lengths)

            total_loss += loss.item()
            num_batches += 1

        return total_loss / max(num_batches, 1)

    def train(
        self,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader] = None,
        epochs: Optional[int] = None,
        save_dir: str = "./checkpoints",
    ):
        """Full training loop."""
        epochs = epochs or self.config.EPOCHS
        os.makedirs(save_dir, exist_ok=True)

        logger.info(f"Starting training for {epochs} epochs")

        for epoch in range(epochs):
            epoch_start = time.time()

            train_loss = self.train_epoch(train_loader)
            val_loss = self.validate(val_loader) if val_loader else train_loss

            self.scheduler.step(val_loss)
            epoch_time = time.time() - epoch_start

            logger.info(
                f"Epoch {epoch + 1}/{epochs}: "
                f"train_loss={train_loss:.4f} | val_loss={val_loss:.4f} | "
                f"time={epoch_time:.1f}s | lr={self.optimizer.param_groups[0]['lr']:.6f}"
            )

            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                checkpoint_path = os.path.join(save_dir, "best_model.pth")
                self._save_checkpoint(checkpoint_path, epoch, val_loss)
                logger.info(f"Best model saved: {checkpoint_path}")
            else:
                self.patience_counter += 1
                if self.patience_counter >= self.config.PATIENCE:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break

            if (epoch + 1) % 10 == 0:
                checkpoint_path = os.path.join(save_dir, f"checkpoint_epoch_{epoch + 1}.pth")
                self._save_checkpoint(checkpoint_path, epoch, val_loss)

        logger.info(f"Training complete. Best val_loss: {self.best_val_loss:.4f}")

    def _save_checkpoint(self, path: str, epoch: int, val_loss: float):
        """Save model checkpoint."""
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "val_loss": val_loss,
            "config": {
                "vocab_size": self.vocab.size,
                "attention_heads": self.config.ATTENTION_HEADS,
                "attention_dim": self.config.ATTENTION_DIM,
                "decoder_hidden": self.config.DECODER_HIDDEN,
            },
        }, path)

    def load_checkpoint(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        logger.info(f"Checkpoint loaded from {path} (epoch {checkpoint.get('epoch', '?')})")


def main():
    parser = argparse.ArgumentParser(description="Train lip-reading model")
    parser.add_argument("--data_dir", type=str, required=True, help="Training data directory")
    parser.add_argument("--val_dir", type=str, default=None, help="Validation data directory")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--save_dir", type=str, default="./checkpoints")
    parser.add_argument("--resume", type=str, default=None, help="Resume from checkpoint")
    args = parser.parse_args()

    config = ModelConfig()
    config.EPOCHS = args.epochs
    config.BATCH_SIZE = args.batch_size
    config.LEARNING_RATE = args.lr

    trainer = LipReadingTrainer(config)

    if args.resume:
        trainer.load_checkpoint(args.resume)

    vocab = CharacterVocab()
    train_dataset = LipReadingDataset(args.data_dir, vocab, max_frames=config.INPUT_FRAMES)
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        num_workers=4, collate_fn=collate_fn, pin_memory=True,
    )

    val_loader = None
    if args.val_dir:
        val_dataset = LipReadingDataset(args.val_dir, vocab, max_frames=config.INPUT_FRAMES)
        val_loader = DataLoader(
            val_dataset, batch_size=args.batch_size, shuffle=False,
            num_workers=4, collate_fn=collate_fn, pin_memory=True,
        )

    trainer.train(train_loader, val_loader, epochs=args.epochs, save_dir=args.save_dir)


if __name__ == "__main__":
    main()
