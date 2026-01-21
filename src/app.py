def compute_metric(value: int) -> int:
    if value < 0:
        raise ValueError("value must be non-negative")
    return value * 2


def main() -> None:
    print("ok")


if __name__ == "__main__":
    main()
