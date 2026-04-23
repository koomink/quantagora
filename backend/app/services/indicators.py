from math import sqrt


def sma(values: list[float], period: int) -> list[float | None]:
    results: list[float | None] = []
    if period <= 0:
        raise ValueError("period must be positive")
    window_sum = 0.0
    for index, value in enumerate(values):
        window_sum += value
        if index >= period:
            window_sum -= values[index - period]
        if index + 1 < period:
            results.append(None)
        else:
            results.append(window_sum / period)
    return results


def ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    results: list[float | None] = []
    multiplier = 2.0 / (period + 1)
    ema_value: float | None = None
    for index, value in enumerate(values):
        if index + 1 < period:
            results.append(None)
            continue
        if ema_value is None:
            ema_value = sum(values[index + 1 - period : index + 1]) / period
        else:
            ema_value = ((value - ema_value) * multiplier) + ema_value
        results.append(ema_value)
    return results


def roc(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    results: list[float | None] = []
    for index, value in enumerate(values):
        if index < period:
            results.append(None)
            continue
        prior = values[index - period]
        if prior == 0:
            results.append(None)
            continue
        results.append(((value / prior) - 1.0) * 100.0)
    return results


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < 2:
        return [None for _ in values]

    gains = [0.0]
    losses = [0.0]
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    results: list[float | None] = [None for _ in values]
    avg_gain = 0.0
    avg_loss = 0.0
    for index in range(1, len(values)):
        if index < period:
            avg_gain += gains[index]
            avg_loss += losses[index]
            continue
        if index == period:
            avg_gain = (avg_gain + gains[index]) / period
            avg_loss = (avg_loss + losses[index]) / period
        else:
            avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period
        if avg_loss == 0:
            results[index] = 100.0
            continue
        relative_strength = avg_gain / avg_loss
        results[index] = 100.0 - (100.0 / (1.0 + relative_strength))
    return results


def macd(
    values: list[float],
    *,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    macd_line: list[float | None] = []
    macd_inputs: list[float] = []
    macd_indexes: list[int] = []
    for index, (fast_value, slow_value) in enumerate(zip(fast, slow, strict=True)):
        if fast_value is None or slow_value is None:
            macd_line.append(None)
            continue
        value = fast_value - slow_value
        macd_line.append(value)
        macd_inputs.append(value)
        macd_indexes.append(index)

    signal_inputs = ema(macd_inputs, signal_period)
    signal_line: list[float | None] = [None for _ in values]
    histogram: list[float | None] = [None for _ in values]
    for index, signal_value in zip(macd_indexes, signal_inputs, strict=True):
        signal_line[index] = signal_value
        if signal_value is not None and macd_line[index] is not None:
            histogram[index] = macd_line[index] - signal_value
    return macd_line, signal_line, histogram


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not highs or len(highs) != len(lows) or len(highs) != len(closes):
        raise ValueError("price series lengths must match and be non-empty")

    true_ranges: list[float] = []
    for index, (high, low, _close) in enumerate(zip(highs, lows, closes, strict=True)):
        if index == 0:
            true_ranges.append(high - low)
            continue
        prev_close = closes[index - 1]
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))

    results: list[float | None] = [None for _ in true_ranges]
    atr_value: float | None = None
    for index, value in enumerate(true_ranges):
        if index + 1 < period:
            continue
        if atr_value is None:
            atr_value = sum(true_ranges[index + 1 - period : index + 1]) / period
        else:
            atr_value = ((atr_value * (period - 1)) + value) / period
        results[index] = atr_value
    return results


def realized_volatility(values: list[float], period: int = 20) -> list[float | None]:
    if period <= 1:
        raise ValueError("period must be greater than 1")
    returns = [None]
    for index in range(1, len(values)):
        previous = values[index - 1]
        if previous == 0:
            returns.append(None)
            continue
        returns.append((values[index] / previous) - 1.0)

    results: list[float | None] = [None for _ in values]
    for index in range(len(values)):
        if index < period:
            continue
        window = [value for value in returns[index + 1 - period : index + 1] if value is not None]
        if len(window) < period:
            continue
        mean_return = sum(window) / len(window)
        variance = sum((value - mean_return) ** 2 for value in window) / len(window)
        results[index] = sqrt(variance) * sqrt(252)
    return results
