# -*- coding: utf-8 -*-
"""
    glickoTR (Tennis Rating)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    A modified Glicko2 rating system tailored for tennis, incorporating
    game score margins and weighting for match completeness.

    Based on the original glicko2 implementation:
    :copyright: (c) 2012 by Heungsub Lee
    :license: BSD, see LICENSE for more details.
"""
import math

__version__ = '0.1.dev'

# Constants for match status
COMPLETED = 'completed'
RETIRED = 'retired'
WALKOVER = 'walkover'

# Default Glicko-2 parameters
MU = 1500
PHI = 350
SIGMA = 0.06
TAU = 1  # System constant (recommend 0.3 to 1.2) - controls volatility change speed
EPSILON = 0.000001 # Convergence tolerance


class Rating(object):
    """Stores a player's rating details: mu (rating), phi (rating deviation),
    and sigma (rating volatility)."""
    def __init__(self, mu=MU, phi=PHI, sigma=SIGMA):
        self.mu = mu
        self.phi = phi
        self.sigma = sigma

    def __repr__(self):
        c = type(self)
        args = (c.__module__, c.__name__, self.mu, self.phi, self.sigma)
        return '%s.%s(mu=%.3f, phi=%.3f, sigma=%.3f)' % args


class Glicko2(object):
    """
    The Glicko2 calculation engine, modified for tennis results.

    Takes into account game scores and match completeness.
    """
    def __init__(self, mu=MU, phi=PHI, sigma=SIGMA, tau=TAU, epsilon=EPSILON):
        self.mu = mu
        self.phi = phi
        self.sigma = sigma
        self.tau = tau
        self.epsilon = epsilon

    def create_rating(self, mu=None, phi=None, sigma=None):
        """Creates a Rating object, using system defaults if not provided."""
        if mu is None:
            mu = self.mu
        if phi is None:
            phi = self.phi
        if sigma is None:
            sigma = self.sigma
        return Rating(mu, phi, sigma)

    def scale_down(self, rating, ratio=173.7178):
        """Converts a Rating object to the internal Glicko-2 scale."""
        mu = (rating.mu - self.mu) / ratio
        phi = rating.phi / ratio
        return self.create_rating(mu, phi, rating.sigma)

    def scale_up(self, rating, ratio=173.7178):
        """Converts a Rating object from the internal Glicko-2 scale back
        to the original scale."""
        mu = rating.mu * ratio + self.mu
        phi = rating.phi * ratio
        # Clamp the final rating (mu) to a reasonable range
        min_rating = 0
        max_rating = 10000
        mu = max(min_rating, min(mu, max_rating))
        return self.create_rating(mu, phi, rating.sigma)

    def reduce_impact(self, rating):
        """The original Glicko `g(RD)` function. Reduces the impact of games
        as a function of an opponent's RD (phi). High opponent RD = lower impact."""
        # This uses the rating deviation (phi) on the Glicko-2 scale
        return 1. / math.sqrt(1 + (3 * rating.phi ** 2) / (math.pi ** 2))

    def expect_score(self, rating, other_rating, impact):
        """The original Glicko `E` function. Calculates the expected probability
        of the player winning against the opponent."""
        # ratings are on the Glicko-2 scale
        score = 1. / (1 + math.exp(-impact * (rating.mu - other_rating.mu)))
        # Clamp score to prevent it from being exactly 0 or 1, which causes variance_inv issues
        # Use a slightly larger epsilon than the main convergence one if needed
        clamp_epsilon = 1e-1 #####
        return max(clamp_epsilon, min(score, 1.0 - clamp_epsilon))

    def _calculate_match_weight(self, status, player_games, opponent_games):
        """Determines the weight of a match based on its status and completeness.
        - Completed matches have full weight (1.0).
        - Walkovers have zero weight (0.0).
        - Retirements have partial weight, increasing with games played, capped.
        """
        if status == WALKOVER:
            return 0.0
        elif status == COMPLETED:
            return 1.0
        elif status == RETIRED:
            total_games = player_games + opponent_games
            if total_games <= 0: # Avoid division by zero / nonsensical input
                return 0.0
            # Linear ramp up to 18 games (approx 2 sets), capped at 0.8 weight
            # This ensures completed matches always have higher weight.
            threshold_games = 18.0
            max_retirement_weight = 0.8
            weight = min(1.0, total_games / threshold_games) * max_retirement_weight
            return weight
        else:
            # Unknown status, treat as zero weight for safety
            return 0.0

    def determine_sigma(self, rating, difference, variance):
        """The iterative procedure to determine the new volatility (sigma').
        This is unchanged from the standard Glicko-2 algorithm.
        Rating object should be on the Glicko-2 scale."""
        phi = rating.phi
        difference_squared = difference ** 2
        # 1. Let a = ln(sigma^2), and define f(x)
        alpha = math.log(rating.sigma ** 2)

        def f(x):
            """This function is derived from the Glicko-2 paper, used to find
            the new sigma."""
            exp_x = math.exp(x)
            tmp = phi ** 2 + variance + exp_x
            if tmp < 1e-15: # Avoid division by zero or near-zero
                # This case should be rare but could happen if variance is extremely small
                # and exp(x) is also very small. Returning a large negative value
                # should push the search away from this region.
                return -1.0 / (self.tau**2) # Or some other robust handling

            a = exp_x * (difference_squared - phi**2 - variance - exp_x) / (2 * tmp ** 2)
            b = (x - alpha) / (self.tau ** 2)
            return a - b

        # 2. Set the initial values of the iterative algorithm.
        a = alpha
        if difference_squared > phi ** 2 + variance:
            b = math.log(difference_squared - phi ** 2 - variance)
        else:
            k = 1
            # Check bounds to prevent infinite loop if f never goes negative
            max_k = 100 # Safety break
            while k < max_k and f(alpha - k * math.sqrt(self.tau ** 2)) >= 0:
                k += 1
            b = alpha - k * math.sqrt(self.tau ** 2)
        # 3. Let fA = f(A) and f(B) = f(B)
        f_a, f_b = f(a), f(b)

        # Ensure f_a and f_b have opposite signs for the algorithm to work
        # Add a safety check/adjustment if they don't initially
        if f_a * f_b >= 0:
            # This indicates an issue, potentially numerical instability or unusual inputs.
            # Fallback strategy: Return current sigma or a slightly adjusted value.
            # For now, let's return current sigma; a more robust solution might be needed.
            # Warning: This might happen if variance is extremely high relative to diff^2
            # print(f"Warning: determine_sigma convergence issue (f_a={f_a}, f_b={f_b}). Returning current sigma.")
            return rating.sigma # Fallback

        # 4. While |B-A| > epsilon, carry out the iterative steps (Illinois method variant)
        while abs(b - a) > self.epsilon:
            c = a + (a - b) * f_a / (f_b - f_a)
            f_c = f(c)
            if f_c * f_b < 0:
                a, f_a = b, f_b
            else:
                # Modified update (Illinois method)
                f_a *= f_b / (f_b + f_c) # Prevents division by zero if f_b = -f_c
            b, f_b = c, f_c

            # Safety break for potential infinite loops
            if abs(f_b - f_a) < self.epsilon:
                 break

        # 5. Once |B-A| <= epsilon, set new sigma' = exp(A/2) or exp(B/2)
        # Using b as it's the last calculated point
        return math.exp(b / 2)

    def rate(self, rating, series):
        """Calculates the new rating for a player based on a series of match results
        within a rating period.

        Args:
            rating (Rating): The player's Rating object at the start of the period.
            series (list): A list of tuples representing matches played by the player
                           during the period. Each tuple should be in the format:
                           (player_games_won, opponent_games_won, opponent_rating, match_status)
                           Where opponent_rating is the opponent's Rating object at the
                           start of the period, and match_status is one of
                           COMPLETED, RETIRED, or WALKOVER.

        Returns:
            Rating: The player's new Rating object for the next period.
        """
        # Step 2. Convert rating to Glicko-2 scale
        rating_g2 = self.scale_down(rating)

        # Calculate intermediate values: variance_inv (1/v) and difference (Delta)
        variance_inv = 0
        difference = 0

        if not series:
            # No games played in the period, only update RD based on volatility (Step 6 logic)
            phi_star = math.sqrt(rating_g2.phi ** 2 + rating_g2.sigma ** 2)
            # No change to mu or sigma if no games played
            return self.scale_up(self.create_rating(rating_g2.mu, phi_star, rating_g2.sigma))

        for player_games, opp_games, other_rating_orig, status in series:
            # Calculate weight for this match
            match_weight = self._calculate_match_weight(status, player_games, opp_games)

            if match_weight <= 0:
                continue # Skip walkovers or zero-weight matches

            # Convert opponent rating to Glicko-2 scale
            other_rating_g2 = self.scale_down(other_rating_orig)
            # Calculate opponent impact g(phi)
            impact = self.reduce_impact(other_rating_g2)
            # Calculate expected score E (probability player wins match)
            expected_score = self.expect_score(rating_g2, other_rating_g2, impact)

            # Calculate actual score (game win percentage)
            total_games = player_games + opp_games
            if total_games <= 0:
                 actual_score = 0.5 # Avoid division by zero; treat as draw if 0 games (should be caught by weight)
            else:
                 actual_score = float(player_games) / total_games

            # Accumulate variance_inv and difference, scaled by match_weight
            variance_inv += match_weight * (impact ** 2 * expected_score * (1 - expected_score))
            difference += match_weight * (impact * (actual_score - expected_score))

        # If variance_inv is zero or very close to zero (e.g., only played walkovers),
        # handle similarly to no games played.
        if variance_inv < self.epsilon:
            phi_star = math.sqrt(rating_g2.phi ** 2 + rating_g2.sigma ** 2)
            return self.scale_up(self.create_rating(rating_g2.mu, phi_star, rating_g2.sigma))

        '''
        # Fix 1: Add a threshold check for minimum variance_inv to ensure stability
        practical_min_variance_inv = 1.5e-4 # Threshold for meaningful update #####
        if variance_inv < practical_min_variance_inv:
            # If variance is too small, indicates near-certain outcomes provided little info.
            # Only update RD based on volatility, similar to no games played.
            # print(f"Debug: variance_inv ({variance_inv:.2e}) below threshold. Skipping mu/sigma update.") # Optional debug log
            phi_star = math.sqrt(rating_g2.phi ** 2 + rating_g2.sigma ** 2)
            return self.scale_up(self.create_rating(rating_g2.mu, phi_star, rating_g2.sigma))
        '''

        # Calculate final v and Delta
        variance = 1. / variance_inv
        difference /= variance_inv # This is Delta in the paper

        # Step 5. Determine the new value of sigma
        new_sigma = self.determine_sigma(rating_g2, difference, variance)

        # Step 6. Update the rating deviation to the new pre-rating period value, phi*
        phi_star = math.sqrt(rating_g2.phi ** 2 + new_sigma ** 2)

        # Step 7. Update the rating and RD to the new values, mu' and phi'
        new_phi = 1. / math.sqrt(1. / phi_star ** 2 + 1. / variance)
        new_mu = rating_g2.mu + new_phi ** 2 * difference # difference already includes 1/v^2 factor

        # Step 8. Convert new rating and RD back to original scale
        return self.scale_up(self.create_rating(new_mu, new_phi, new_sigma))

    def rate_tennis_match(self, rating1, rating2, games1, games2, status):
        """Convenience function to calculate updated ratings for both players
        after a single tennis match.

        Args:
            rating1 (Rating): Player 1's rating before the match.
            rating2 (Rating): Player 2's rating before the match.
            games1 (int): Games won by Player 1.
            games2 (int): Games won by Player 2.
            status (str): Match status (COMPLETED, RETIRED, WALKOVER).

        Returns:
            tuple(Rating, Rating): The updated ratings for (Player 1, Player 2).
        """
        # Create the series input for each player's perspective
        series1 = [(games1, games2, rating2, status)]
        series2 = [(games2, games1, rating1, status)] # Note swapped games

        # Calculate new ratings
        new_rating1 = self.rate(rating1, series1)
        new_rating2 = self.rate(rating2, series2)

        return new_rating1, new_rating2

    def quality_1vs1(self, rating1, rating2):
        """Estimates the quality of a match-up (how competitive it is expected to be).
        Lower values mean one player is a heavy favorite. Value near 1 means
        it's expected to be very close. Uses original scale ratings."""
        # Convert to Glicko-2 scale for calculations
        r1_g2 = self.scale_down(rating1)
        r2_g2 = self.scale_down(rating2)
        impact1 = self.reduce_impact(r1_g2)
        impact2 = self.reduce_impact(r2_g2)
        expected_score1 = self.expect_score(r1_g2, r2_g2, impact2) # P1 vs P2 (uses P2 impact)
        expected_score2 = self.expect_score(r2_g2, r1_g2, impact1) # P2 vs P1 (uses P1 impact)

        # Average expected score (how close to 0.5 is the average prediction)
        # A simpler measure might just be based on one player's expected score:
        # quality = 1 - abs(expected_score1 - 0.5) * 2
        # Let's stick to the original implementation's averaging approach:
        expected_score_avg = (expected_score1 + (1.0 - expected_score2)) / 2.0
        # The closer expected_score_avg is to 0.5, the higher the quality.
        quality = 2 * (0.5 - abs(0.5 - expected_score_avg))
        return quality
