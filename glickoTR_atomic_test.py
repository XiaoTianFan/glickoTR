import math
import argparse
import json
from glickoTR import Glicko2, Rating, COMPLETED, RETIRED, WALKOVER # Import necessary items

# Default Glicko-2 parameters (should match glickoTR.py and glicko.ts)
DEFAULT_MU = 1500.0
DEFAULT_PHI = 350.0
DEFAULT_SIGMA = 0.06
SCALING_FACTOR = 173.7178
TAU = 0.5
EPSILON = 0.000001

# Epsilon for clamping expected score (should match glicko.ts)
CLAMP_EPSILON = 1e-10 

def calculate_single_match_update(
    player_rating: Rating,
    opponent_rating: Rating,
    player_games: int,
    opponent_games: int,
    status: str,
    engine: Glicko2
) -> dict:
    """
    Calculates the GlickoTR update for a single match, mirroring the steps
    in the TypeScript calculateGlickoTRUpdate function.
    """

    # Map status string to constants used in Python script
    status_map = {
        "completed": COMPLETED,
        "retired": RETIRED,
        "walkover": WALKOVER
    }
    match_status_const = status_map.get(status.lower(), COMPLETED) # Default to completed if unknown

    # 1. Calculate Match Weight (using the engine's method)
    match_weight = engine._calculate_match_weight(match_status_const, player_games, opponent_games)

    if match_weight <= 0:
        # Return original ratings if match has no weight
        return {
            "player_new": {"mu": player_rating.mu, "phi": player_rating.phi, "sigma": player_rating.sigma},
            "opponent_new": {"mu": opponent_rating.mu, "phi": opponent_rating.phi, "sigma": opponent_rating.sigma}
        }

    # 2. Scale ratings down
    player_g2 = engine.scale_down(player_rating)
    opponent_g2 = engine.scale_down(opponent_rating)

    # === Calculations for Player ===

    # 3. Calculate impact, E, S for player's perspective
    impact_player = engine.reduce_impact(opponent_g2)
    expected_score_player = engine.expect_score(player_g2, opponent_g2, impact_player)
    total_games = player_games + opponent_games
    # Handle division by zero if total_games is 0 (should be caught by weight check, but belt-and-suspenders)
    actual_score_player = 0.5 if total_games <= 0 else player_games / total_games 

    # 4. Calculate variance (v) and difference term for player perspective
    #    This needs to match the intermediate terms used in the TS implementation.
    #    v = 1.0 / (impact^2 * E * (1-E))
    #    variance_inv_term = match_weight * impact^2 * E * (1-E) (used for phi update)
    #    difference_term = match_weight * impact * (S-E) (used for mu update AND sigma determination)
    
    variance_player_inv = (impact_player ** 2) * expected_score_player * (1.0 - expected_score_player)
    # Clamp variance term if E is too close to 0 or 1 (mimicking TS logic where E is clamped)
    # Note: The python expect_score already clamps E, so clamping variance_inv might be redundant
    # variance_player_inv = max(variance_player_inv, 1e-8) # Add small epsilon if needed
    
    variance_player = 1.0 / variance_player_inv if variance_player_inv > 0 else 1e8 # Avoid division by zero, use large variance

    # Clamp variance to prevent instability (matching TS)
    clamped_variance_player = min(variance_player, 1e6) 

    # The difference term used in the mu update and sigma calculation
    diff_term_player = match_weight * impact_player * (actual_score_player - expected_score_player)
    # The variance term passed to determineSigma in TS
    variance_for_sigma_player = clamped_variance_player 
    # The variance inverse term used for the phi update in TS (weighted)
    variance_inv_term_player = match_weight * variance_player_inv

    # 5. Determine new sigma for player
    new_sigma_player = engine.determine_sigma(player_g2, diff_term_player, variance_for_sigma_player)

    # 6. Calculate updated phi* (pre-update RD) for player
    phi_star_player = math.sqrt(player_g2.phi ** 2 + new_sigma_player ** 2)

    # 7. Calculate new phi and mu for player (using weighted variance term for phi update)
    # Formula: new_phi_g2 = 1.0 / sqrt(1.0 / phi_star^2 + weighted_variance_inv)
    new_phi_player_g2 = 1.0 / math.sqrt((1.0 / phi_star_player ** 2) + variance_inv_term_player)
    # Formula: new_mu_g2 = mu_g2 + new_phi_g2^2 * diff_term_player
    new_mu_player_g2 = player_g2.mu + (new_phi_player_g2 ** 2) * diff_term_player

    # 8. Create updated player rating on Glicko-2 scale
    updated_player_g2 = Rating(new_mu_player_g2, new_phi_player_g2, new_sigma_player)

    # === Calculations for Opponent === (Symmetrical)

    # 3. Calculate impact, E, S for opponent's perspective
    impact_opponent = engine.reduce_impact(player_g2)
    expected_score_opponent = engine.expect_score(opponent_g2, player_g2, impact_opponent)
    actual_score_opponent = 1.0 - actual_score_player

    # 4. Calculate variance (v) and difference term for opponent perspective
    variance_opponent_inv = (impact_opponent ** 2) * expected_score_opponent * (1.0 - expected_score_opponent)
    # variance_opponent_inv = max(variance_opponent_inv, 1e-8) # Clamp if needed
    
    variance_opponent = 1.0 / variance_opponent_inv if variance_opponent_inv > 0 else 1e8
    clamped_variance_opponent = min(variance_opponent, 1e6)

    diff_term_opponent = match_weight * impact_opponent * (actual_score_opponent - expected_score_opponent)
    variance_for_sigma_opponent = clamped_variance_opponent
    variance_inv_term_opponent = match_weight * variance_opponent_inv
    
    # 5. Determine new sigma for opponent
    new_sigma_opponent = engine.determine_sigma(opponent_g2, diff_term_opponent, variance_for_sigma_opponent)

    # 6. Calculate updated phi* for opponent
    phi_star_opponent = math.sqrt(opponent_g2.phi ** 2 + new_sigma_opponent ** 2)

    # 7. Calculate new phi and mu for opponent
    new_phi_opponent_g2 = 1.0 / math.sqrt((1.0 / phi_star_opponent ** 2) + variance_inv_term_opponent)
    new_mu_opponent_g2 = opponent_g2.mu + (new_phi_opponent_g2 ** 2) * diff_term_opponent

    # 8. Create updated opponent rating on Glicko-2 scale
    updated_opponent_g2 = Rating(new_mu_opponent_g2, new_phi_opponent_g2, new_sigma_opponent)

    # 9. Scale both new ratings back up
    final_player_rating = engine.scale_up(updated_player_g2)
    final_opponent_rating = engine.scale_up(updated_opponent_g2)

    return {
        "player_new": {"mu": final_player_rating.mu, "phi": final_player_rating.phi, "sigma": final_player_rating.sigma},
        "opponent_new": {"mu": final_opponent_rating.mu, "phi": final_opponent_rating.phi, "sigma": final_opponent_rating.sigma}
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calculate GlickoTR update for a single match.')
    parser.add_argument('--p1_mu', type=float, required=True, help="Player 1 initial mu")
    parser.add_argument('--p1_phi', type=float, required=True, help="Player 1 initial phi (RD)")
    parser.add_argument('--p1_sigma', type=float, required=True, help="Player 1 initial sigma (volatility)")
    parser.add_argument('--p2_mu', type=float, required=True, help="Player 2 initial mu")
    parser.add_argument('--p2_phi', type=float, required=True, help="Player 2 initial phi (RD)")
    parser.add_argument('--p2_sigma', type=float, required=True, help="Player 2 initial sigma (volatility)")
    parser.add_argument('--p1_games', type=int, required=True, help="Games won by Player 1")
    parser.add_argument('--p2_games', type=int, required=True, help="Games won by Player 2")
    parser.add_argument('--status', type=str, required=True, choices=['completed', 'retired', 'walkover'], help="Match status")

    args = parser.parse_args()

    # Initialize the Glicko2 engine with default parameters
    # Ensure these match the parameters used in glickoTR.py and glicko.ts
    engine = Glicko2(mu=DEFAULT_MU, phi=DEFAULT_PHI, sigma=DEFAULT_SIGMA, tau=TAU, epsilon=EPSILON)

    # Create initial Rating objects
    player1 = Rating(mu=args.p1_mu, phi=args.p1_phi, sigma=args.p1_sigma)
    player2 = Rating(mu=args.p2_mu, phi=args.p2_phi, sigma=args.p2_sigma)

    # Calculate the update
    result = calculate_single_match_update(
        player_rating=player1,
        opponent_rating=player2,
        player_games=args.p1_games,
        opponent_games=args.p2_games,
        status=args.status,
        engine=engine
    )

    # Print the result as JSON
    print(json.dumps(result, indent=4)) 