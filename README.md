# GlickoTR: A Modified Glicko-2 Rating System for Tennis

[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

This project implements `glickoTR` (Glicko Tennis Rating), a rating system based on the Glicko-2 algorithm, specifically adapted for tennis matches (UTR-ish Glicko2). It incorporates game score margins and weights matches based on their completeness (e.g., handling retirements and walkovers).

This implementation is derived from the original Python `glicko2` library by Heungsub Lee.

## Features

*   **Tennis-Specific Adjustments:** Uses the game win percentage (`player_games / total_games`) as the match outcome instead of just win/loss.
*   **Match Completeness Weighting:**
    *   `COMPLETED` matches receive full weight (1.0).
    *   `RETIRED` matches receive partial weight based on the number of games played (linearly scaled up to 18 games, capped at 0.8 weight).
    *   `WALKOVER` matches receive zero weight (0.0).
*   **Standard Glicko-2 Mechanics:** Utilizes the core Glicko-2 concepts of rating (μ), rating deviation (φ), and volatility (σ).
*   **Convenience Functions:** Includes methods for rating single matches (`rate_tennis_match`) and batch processing results over a rating period (`rate`).
*   **Match Quality Estimation:** Provides a function (`quality_1vs1`) to estimate how competitive a potential matchup is likely to be.

## Installation

Currently, this is a single-file module. To use it, simply place `glickoTR.py` in your project directory or ensure it's in your Python path.

**Dependencies:**
*   Python 3.x
*   `math` (standard library)

## Usage

### 1. Initialize the Environment and Ratings

```python
from glickoTR import Glicko2, Rating, COMPLETED, RETIRED, WALKOVER

# Initialize the Glicko2 engine (can customize parameters)
env = Glicko2(tau=0.5) # Example: Lower tau for slower volatility changes

# Create initial ratings for players
player1_rating = env.create_rating(mu=1500, phi=200, sigma=0.06)
player2_rating = env.create_rating(mu=1400, phi=150, sigma=0.05)
player3_rating = env.create_rating(mu=1600, phi=300, sigma=0.07)
```

### 2. Update Ratings After a Single Match

Use `rate_tennis_match` for simplicity.

```python
# Example: Player 1 beats Player 2, 6-3, 6-4 (Completed match)
games1 = 12
games2 = 7
status = COMPLETED

new_player1_rating, new_player2_rating = env.rate_tennis_match(
    player1_rating, player2_rating, games1, games2, status
)

print(f"Old P1 Rating: {player1_rating}")
print(f"New P1 Rating: {new_player1_rating}")
print(f"Old P2 Rating: {player2_rating}")
print(f"New P2 Rating: {new_player2_rating}")

# Example: Player 3 leads Player 1, 6-2, 3-0, then Player 1 retires
games3 = 9 # 6 + 3
games1_retired = 2 # 2 + 0
status_retired = RETIRED

# Ratings used should be from the start of the rating period
# Assuming this match happened *after* the P1 vs P2 match above,
# we might use new_player1_rating here if starting a new period,
# or the original player1_rating if part of the same period.
# For this example, let's assume it's in the same period:
new_player3_rating, updated_player1_rating_after_ret = env.rate_tennis_match(
    player3_rating, player1_rating, games3, games1_retired, status_retired
)

print(f"Old P3 Rating: {player3_rating}")
print(f"New P3 Rating: {new_player3_rating}")
print(f"P1 Rating after retirement loss: {updated_player1_rating_after_ret}")
```

### 3. Update Ratings Over a Period (Multiple Matches)

Use the `rate` method with a list of match results for a specific player.

```python
# Assume player1 played two matches in this period:
# 1. Lost to Player 3 (6-2, 3-0 RET - as above)
# 2. Beat Player 2 (12-7 COMPLETED - as above)

# Ratings used for opponents must be *their* rating at the *start* of the period
player1_series = [
    # (player_games, opp_games, opp_rating_start_period, status)
    (games1_retired, games3, player3_rating, status_retired), # Loss vs P3
    (games1, games2, player2_rating, COMPLETED)             # Win vs P2
]

# Calculate Player 1's rating after the entire period
final_player1_rating_period = env.rate(player1_rating, player1_series)

print(f"Player 1 rating after period: {final_player1_rating_period}")

# You would perform similar calculations for Player 2 and Player 3 based on their matches.
# For Player 3's series, the match against Player 1 would look like:
# (games3, games1_retired, player1_rating, status_retired)
```

### 4. Check Match Quality

```python
quality = env.quality_1vs1(player1_rating, player2_rating)
print(f"Estimated quality of P1 vs P2 matchup: {quality:.3f}") # Closer to 1.0 means more competitive
```

**Note:** For more detailed examples and simulations, please refer to the `glickoTR_simulation_test.ipynb` notebook included in this repository.

## Key Parameters

The Glicko-2 system uses several parameters:

*   `mu` (Default: 1500): The initial average rating.
*   `phi` (Default: 350): The initial rating deviation (uncertainty). Higher means more uncertainty.
*   `sigma` (Default: 0.06): The initial rating volatility. Higher means the rating is expected to fluctuate more.
*   `tau` (Default: 1.0): System constant controlling how quickly volatility changes. Recommended range 0.3 to 1.2. Lower values slow down volatility updates.
*   `epsilon` (Default: 0.000001): Convergence tolerance for iterative calculations.

These can be set when creating the `Glicko2` environment instance or overridden when creating individual `Rating` objects.

## License

This project includes code derived from Heungsub Lee's `glicko2` implementation, which is licensed under the BSD 3-Clause license.

The modifications and additional code specific to `glickoTR` (Copyright (c) 2024, Xiaotian Fan, As33) are also released under the **BSD 3-Clause License**.

See the `LICENSE` file for the full license text.

## Acknowledgments

*   Thanks to **Heungsub Lee** for the original Python `glicko2` implementation.
*   Based on the Glicko-2 rating system developed by **Mark Glickman**. 