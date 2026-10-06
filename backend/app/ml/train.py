"""Compatibility entrypoint for the actual PyTorch/shared-evaluation pipeline."""


def train() -> None:
    from ml.train_all import main

    main()


if __name__ == "__main__":
    train()
