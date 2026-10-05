"""Expanding-window walk-forward construction, embargo enforcement, and
no-future-leakage guarantees."""

from training.market.common import walk_forward_windows


def test_windows_expand_chronologically_from_a_fixed_start():
    windows = walk_forward_windows(n_obs=1000, initial_train=200, embargo=5, test_window=50)
    assert len(windows) > 1
    for w in windows:
        assert w["train_start"] == 0  # expanding, never rolling
    train_ends = [w["train_end"] for w in windows]
    assert train_ends == sorted(train_ends)
    assert len(set(train_ends)) == len(train_ends)  # strictly increasing


def test_embargo_gap_is_enforced_between_train_and_test():
    windows = walk_forward_windows(n_obs=1000, initial_train=200, embargo=7, test_window=50)
    for w in windows:
        assert w["test_start"] - w["train_end"] == 7


def test_test_window_size_is_respected():
    windows = walk_forward_windows(n_obs=1000, initial_train=200, embargo=5, test_window=50)
    for w in windows:
        assert w["test_end"] - w["test_start"] == 50


def test_no_window_exceeds_available_observations():
    n_obs = 500
    windows = walk_forward_windows(n_obs=n_obs, initial_train=200, embargo=5, test_window=50)
    for w in windows:
        assert w["test_end"] <= n_obs


def test_train_and_test_never_overlap_and_test_never_precedes_train():
    """The direct proof of no future leakage: every window's test indices
    are strictly greater than every one of its own train indices, with the
    embargo gap in between never assigned to either set."""
    windows = walk_forward_windows(n_obs=1000, initial_train=200, embargo=5, test_window=50)
    for w in windows:
        train_indices = set(range(w["train_start"], w["train_end"]))
        test_indices = set(range(w["test_start"], w["test_end"]))
        embargo_indices = set(range(w["train_end"], w["test_start"]))

        assert train_indices.isdisjoint(test_indices)
        assert train_indices.isdisjoint(embargo_indices)
        assert test_indices.isdisjoint(embargo_indices)
        assert max(train_indices) < min(embargo_indices) if embargo_indices else True
        assert max(train_indices) < min(test_indices)


def test_insufficient_data_produces_no_windows():
    """Edge case: fewer observations than the initial training window
    alone requires -- must return an empty list, never a malformed window."""
    windows = walk_forward_windows(n_obs=100, initial_train=200, embargo=5, test_window=50)
    assert windows == []


def test_exactly_enough_data_for_one_window():
    windows = walk_forward_windows(n_obs=255, initial_train=200, embargo=5, test_window=50)
    assert len(windows) == 1
    assert windows[0] == {"train_start": 0, "train_end": 200, "test_start": 205, "test_end": 255}
