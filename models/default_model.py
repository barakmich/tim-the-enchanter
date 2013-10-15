from util import Bernoulli


# Models work like this; feel free to inherit from BaseModel to get the
# necessary helpful things.
#
# Instance variables of models represent unknowns or random data. The important
# calls are
# * player_sees_player_and_claims
# * votes
# * mission
# And that's it! Delegate to other functions as necessary (see the example
# role-based map below) These functions should return one of the following,
# depending on the circumstance:
# * True -- This set of statements could totally happen (or randomness chose
#   that it did)
#
# * False -- This set of statements could happen, but is unlikely (or
#   randomness chose that it didn't)
#
# * None -- This set of statements could NEVER happen, please remove them from
#   consideration.

class BaseModel(object):
    def __init__(self, game):
        self.game = game
        self.deal = []

#  These are helper functions -- do not override
    def set_deal(self, deal):
        self.deal = deal

    def is_good(self, player, round):
        return self.game.player_is_good(self.deal, player, round)

    def is_role(self, player, role):
        return self.game.player_role(self.deal, player) == role

    def player_role(self, player):
        return self.game.player_role(self.deal, player)

#  Override these!
    def player_sees_player_and_claims(self, p1, p2, claim, rnd):
        return True

    def mission(self, team, fails, must_fail, rnd):
        return True

    def votes(self, team, votes, fail_req, rnd):
        return True


class DefaultModel(BaseModel):
    def __init__(self, game):
        super(DefaultModel, self).__init__(game)

        self.lady_will_duck = Bernoulli(0.7)
        self.mission_ducks_on_round = [None] * 5
        self.mission_ducks_on_round[0] = Bernoulli(0.5)
        self.mission_ducks_on_round[1] = Bernoulli(0.5)
        self.mission_ducks_on_round[2] = Bernoulli(0.5)
        self.mission_ducks_on_round[3] = Bernoulli(0.0)
        self.mission_ducks_on_round[4] = Bernoulli(0.0)
        self.ignorance_on_round = [None] * 5
        self.ignorance_on_round[0] = Bernoulli(0.9)
        self.ignorance_on_round[1] = Bernoulli(0.7)
        self.ignorance_on_round[2] = Bernoulli(0.5)
        self.ignorance_on_round[3] = Bernoulli(0.3)
        self.ignorance_on_round[4] = Bernoulli(0.3)
        self.merlin_ignorance = Bernoulli(0.2)

    def player_sees_player_and_claims(self, p1, p2, claim, rnd):
        if self.is_good(p1, rnd) or self.is_role(p1, "Mordred"):
            if self.is_good(p2, rnd) == claim:
                return True
            else:
                return None
        else:
            if claim is True:
                return self.lady_will_duck.rand()
            if claim is False:
                return not self.lady_will_duck.rand()

    def mission(self, team, fails, must_fail, rnd):
        n_actually_good_people = sum(
            [int(self.is_good(x, rnd)) for x in team])
        n_spies = len(team) - n_actually_good_people
        if n_spies == 0:
            if fails != 0:
                return None
            else:
                return True
        else:
            if fails == 0:
                if must_fail:
                    return None
                duck = False
                for i in range(n_spies - fails):
                    duck = duck or self.mission_ducks_on_round[rnd].rand()
                    return duck
            else:
                if fails > n_spies:
                    return None
                return True

    def votes(self, team, votes, fail_req, rnd):
        n_actually_good_people = sum(
            [int(self.is_good(x, rnd)) for x in team])
        n_spies = len(team) - n_actually_good_people
        could_happen = True
        for player, vote in enumerate(votes):
            role = self.player_role(player)
            if role in special_votes:
                if special_votes[role](self, player, team,
                                       votes, fail_req, rnd):
                    continue
                else:
                    return False
            elif player in team:
                continue
            elif self.is_good(player, rnd):
                if n_spies > fail_req - 1:
                    if vote == 1:
                        if self.ignorance_on_round[rnd].rand():
                            continue
                        else:
                            return False
                    else:
                        if vote == 0:
                            if self.ignorance_on_round[rnd].rand():
                                continue
                            else:
                                return False
                        else:
                            if n_spies < fail_req:
                                if vote == 1:
                                    if self.ignorance_on_round[rnd].rand():
                                        continue
                                    else:
                                        return False
                                else:
                                    if vote == 0:
                                        if self.ignorance_on_round[rnd].rand():
                                            continue
                                        else:
                                            return False
            return could_happen


def merlin_vote(model, player_id, team, votes, fail_req, r):
    n_actually_good_people = sum(
        [int(model.is_good(x, r)) for x in team])
    n_spies = len(team) - n_actually_good_people
    roles = [model.player_role(x) for x in team]
    if "Mordred" in roles:
        n_spies = n_spies - 1

    if player_id in team:
        return True
    # At this point, this is the number of spies Merlin counts
    if n_spies == 0:
        if votes[player_id] == 0:
            # Voted down an apparently good team. Ignore this.
            return True
        if votes[player_id] == 1:
            if model.merlin_ignorance.rand():
                return False
            return True
    elif n_spies == 1:
        # He'll either duck or vote it down. Either is fine
        return True
    elif n_spies > 1 and fail_req == 1 and r > 2:
        # Even a well-played Merlin would never allow two spies on.
        # Unless there's more than one fail required. Then he might
        # duck.
        if votes[player_id] == 0:
            return True
        if votes[player_id] == 1:
            return False
    return True


def mordred_vote(game, player_id, team, votes, fail_req, r):
    n_actually_good_people = sum(
        [int(game.is_good(x, r)) for x in team])
    n_spies = len(team) - n_actually_good_people
    roles = [game.player_role(x) for x in team]
    if "Oberon" in roles:
        n_spies = n_spies - 1

    if player_id in team:
        return True
    # At this point, this is the number of spies Mordred knows.
    if n_spies == 0:
        # The chance that merlin doesn't know Mordred is 1 - Merlin's ignorance
        # Read this as "if Merlin is not ignorant of my role"
        if not game.merlin_ignorance.rand():
            if votes[player_id] == 1:
                return False
            else:
                return True
        # Merlin is ignorant...
        else:
            # Vote it up or down, doesn't matter, both could happen
            return True
    elif n_spies == 1:
        # He'll either duck or vote it down. Either is fine
        return True
    elif n_spies > 1:
        # Never vote up a team of more than one spy, unless fail_req is high
        if fail_req > 1:
            return True
        else:
            return False
    return True

special_votes = {
    "Merlin": merlin_vote,
    "Mordred": mordred_vote
}
