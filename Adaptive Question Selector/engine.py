"""
Bayesian Knowledge Tracing Engine
Implements the standard BKT model with 4 parameters:
  P(L0) — initial probability of knowing the skill
  P(T)  — probability of transitioning from not-knowing to knowing
  P(S)  — probability of slipping (know but answer wrong)
  P(G)  — probability of guessing (don't know but answer correctly)
"""


class BKTEngine:
    def __init__(
        self,
        p_l0: float = 0.1,
        p_transit: float = 0.1,
        p_slip: float = 0.1,
        p_guess: float = 0.2,
    ):
        self.p_l0 = p_l0
        self.p_transit = p_transit
        self.p_slip = p_slip
        self.p_guess = p_guess

    def update(self, p_mastery: float, correct: int) -> float:
        """
        Update mastery estimate given an observed response.
        correct: 1 = correct, 0 = incorrect
        Returns updated P(L_t).
        """
        p_l = p_mastery

        if correct == 1:
            # P(L | correct) = P(correct | L) * P(L) / P(correct)
            p_correct_given_l = 1 - self.p_slip
            p_correct_given_not_l = self.p_guess
        else:
            # P(L | incorrect)
            p_correct_given_l = self.p_slip
            p_correct_given_not_l = 1 - self.p_guess

        numerator = p_correct_given_l * p_l
        denominator = numerator + p_correct_given_not_l * (1 - p_l)

        if denominator == 0:
            p_l_given_obs = p_l
        else:
            p_l_given_obs = numerator / denominator

        # Apply learning (transition)
        p_l_next = p_l_given_obs + (1 - p_l_given_obs) * self.p_transit

        return round(min(max(p_l_next, 0.0), 1.0), 6)

    def predict_correct(self, p_mastery: float) -> float:
        """Probability of answering correctly given current mastery."""
        return p_mastery * (1 - self.p_slip) + (1 - p_mastery) * self.p_guess

    def is_mastered(self, p_mastery: float, threshold: float = 0.95) -> bool:
        return p_mastery >= threshold

    def bulk_update(self, p_mastery: float, responses: list[int]) -> list[float]:
        """Apply a sequence of responses and return trajectory."""
        trajectory = [p_mastery]
        p = p_mastery
        for r in responses:
            p = self.update(p, r)
            trajectory.append(p)
        return trajectory
