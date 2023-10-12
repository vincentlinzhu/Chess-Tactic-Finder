import math


def win(value: float) -> float:
    # https://lichess.org/page/accuracy
    return min(1.0, max(0.0, 0.50 + 0.50 * (2 / (1 + math.exp(-0.368208 * value)) - 1)))


def accuracy(win_difference: float) -> float:
    # https://lichess.org/page/accuracy
    return min(1.0, max(0.0, 1.031668 * math.exp(-4.354 * win_difference) - 0.031668))
