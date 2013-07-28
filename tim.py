import pymc as mc
import functools
import itertools
from collections import defaultdict as dd
import pprint
import numpy


def ResistanceGame(n_players):
    full_set = [("G1", True), ("G2", True), ("G3", True),
                ("E1", False), ("E2", False), ("G4", True),
                ("E3", False), ("G5", True), ("G6", True), ("E4", False)]
    return full_set[:n_players]


def BuildNbyNBeliefMatrix(id, n_players):
    all_vars = []
    matrix = []
    for player_id in range(n_players):
        vec = mc.Uniform("%d_trust_%d" % (id, player_id),
                         0.0, 1.0,
                         trace=True,
                         size=n_players,
                         value=(numpy.ones(n_players) * (1.0 / n_players)))
        matrix.append(vec)
        all_vars.append(vec)

    # Enforce that there's only one role for each player.
    for i, player_vec in enumerate(matrix):
        @mc.potential
        def obs_one_role(player_vec=player_vec):
            return mc.distributions.normal_like(
                sum(player_vec),
                1.0,
                100)
        all_vars.append(obs_one_role)

    # Enforce that there's only one player per role.
    for i in range(n_players):
        @mc.potential
        def obs_one_per_role(matrix=matrix):
            return mc.distributions.normal_like(
                sum([vec[i] for vec in matrix]),
                1.0,
                100)
        all_vars.append(obs_one_per_role)

    return matrix, all_vars


class Player(object):
    ''' Representing all that the player is and knows '''
    def __init__(self, id, game):
        self.id = id
        self.game = game
        self.all_vars = []
        self.build_belief_matrix()

    def side(self):
        return self.side_var

    def role(self):
        return self.role_var

    def build_belief_matrix(self):
        self.matrix, self.all_vars = \
            BuildNbyNBeliefMatrix(self.id, self.game.n_players)

        # Enforce that the player completely knows her own role.
        @mc.potential
        def knows(deck_var=self.game.deck_var, matrix=self.matrix):
            role_id = self.game.player_role_for_deck_var(deck_var, self.id)
            return mc.distributions.normal_like(
                matrix[self.id][role_id],
                1.0,
                100)
        self.all_vars.append(knows)

    def get_role_belief_for(self, player_id, role_id):
        return self.matrix[player_id][role_id]


class DeceptionGame(object):
    def __init__(self, player_array):
        self.player_array = player_array
        self.all_permutations = list(itertools.permutations(player_array))
        self.deck_var = mc.DiscreteUniform("deal", 0,
                                           len(self.all_permutations) - 1)
        self.n_players = len(player_array)
        self.model = None

        self.player_side_vars = []
        self.player_role_vars = []
        self.role_ids = {}
        self.role_side = {}

        i = 0

        for card in player_array:
            role, good = card
            self.role_ids[role] = i
            self.role_side[i] = good
            i += 1

        def player_side(x, role):
            if self.role_side[role]:
                return True
            return False

        def player_role(x, deck_var=self.deck_var):
            role_str = self.all_permutations[deck_var][x][0]
            return int(self.role_ids[role_str])

        self.players = []

        for x in range(self.n_players):
            role = mc.Deterministic(eval=functools.partial(player_role, x),
                                    name="player_role_%d" % x,
                                    parents={"deck_var": self.deck_var},
                                    doc="Who is player %d?" % x,
                                    dtype=int,
                                    trace=True,
                                    plot=False)
            self.player_role_vars.append(role)

            side = mc.Deterministic(eval=functools.partial(
                                    player_side, x),
                                    name="player_side_%d" % x,
                                    parents={"role": role},
                                    doc="Is player %d good?" % x,
                                    dtype=bool,
                                    trace=True,
                                    plot=False)

            self.player_side_vars.append(side)
            #self.players.append(Player(x, self))

        self.lady_will_duck = mc.Bernoulli("lady_will_duck", 0.5)
        self.team_duck = [None] * 5
        self.team_duck[0] = mc.Bernoulli("team_duck_1", 0.8)
        self.team_duck[1] = mc.Bernoulli("team_duck_2", 0.6)
        self.team_duck[2] = mc.Bernoulli("team_duck_3", 0.4)
        self.team_duck[3] = mc.Bernoulli("team_duck_4", 0.2)
        self.team_duck[4] = mc.Bernoulli("team_duck_5", 0.0)

        self.observations = []
        self.tid = 0

    def get_role_id_for(self, name):
        return self.role_ids[name]

    def role_id_is_good(self, role_id):
        return self.role_side[role_id]

    def player_good_for_deck_var(self, index, player):
        return self.all_permutations[index][player][1]

    def player_role_for_deck_var(self, index, player):
        return self.get_role_id_for(self.all_permutations[index][player][0])

    def player_sees_player_and_claims(self, player_view, player_give, claim):
        transaction = []
        total_len = len(self.all_permutations)
        for i in range(len(self.all_permutations)):
            self.deck_var.value = (5119 * i) % total_len
            try:
                @mc.potential
                def claims(deck_var=self.deck_var, will_duck=self.lady_will_duck):
                    if self.player_good_for_deck_var(deck_var, player_view) or will_duck:
                        if self.player_good_for_deck_var(deck_var, player_give) == claim:
                            return 0.0
                        else:
                            return -numpy.inf
                    else:
                        if self.player_good_for_deck_var(deck_var, player_give) == claim:
                            return -numpy.inf
                        else:
                            return 0.0

                        return -numpy.inf
            except mc.ZeroProbability:
                continue

        transaction.append(claims)
        self.observations.append(transaction)
        self.tid += 1

    def add_known_side(self, player_id, is_good):
        transaction = []
        total_len = len(self.all_permutations)
        for i in range(len(self.all_permutations)):
            self.deck_var.value = (5119 * i) % total_len
            try:
                @mc.potential
                def obs(deck_var=self.deck_var):
                    x = float(self.player_good_for_deck_var(deck_var, player_id)) - \
                            float(is_good)
                    return mc.distributions.normal_like(x, 0.0, 10000)
            except mc.ZeroProbability:
                continue
            break

        transaction.append(obs)
        self.observations.append(transaction)
        self.tid += 1

    def add_known_role(self, player_id, role_str):
        transaction = []
        known_role_id = self.get_role_id_for(role_str)
        total_len = len(self.all_permutations)
        for i in range(len(self.all_permutations)):
            self.deck_var.value = (5119 * i) % total_len
            try:
                @mc.potential
                def role(deck_var=self.deck_var):
                    x = self.player_role_for_deck_var(deck_var, player_id) \
                            - known_role_id
                    return mc.distributions.normal_like(x, 0.0, 10000)

            except mc.ZeroProbability:
                continue
            break

        transaction.append(role)
        self.observations.append(transaction)
        self.tid += 1

    def build_team(self, team, votes, required_success):
        transaction = []

        for voter in range(self.n_players):
            total_len = len(self.all_permutations)
            for i in range(len(self.all_permutations)):
                self.deck_var.value = (5119 * i) % total_len
                try:
                    @mc.potential
                    def build_team(deck_var=self.deck_var):
                        voter_is_good = self.player_good_for_deck_var(deck_var, voter)
                        if voter_is_good:
                            return mc.distributions.normal_like(x - n_successes, 0.0, 1000)
                        else:
                            return mc.distributions.normal_like(x - required_success, len(team) -
                    team_votes.name = "voter_%d_tid%d" % (voter, self.tid)

                except mc.ZeroProbability:
                    continue
                break

            transaction.append(team_votes)
        self.observations.append(transaction)
        self.tid += 1
    def team_and_successes(self, team, n_successes, mandatory, r):
        transaction = []

        total_len = len(self.all_permutations)
        for i in range(len(self.all_permutations)):
            self.deck_var.value = (5119 * i) % total_len
            try:
                @mc.potential
                def team_votes(deck_var=self.deck_var, team_duck=self.team_duck[r - 1]):
                    team_allegience = [self.player_good_for_deck_var(deck_var, x)
                                             for x in team]
                    for i, al in enumerate(team_allegience):
                        if al is True:
                            continue
                        else:
                            if not mandatory and team_duck:
                                print "Ducking"
                                team_allegience[i] = True

                    x = sum([float(x) for x in team_allegience])
                    return mc.distributions.normal_like(x - n_successes, 0.0, 1000)
                team_votes.name = "team_votes_tid%d" % self.tid

            except mc.ZeroProbability:
                continue
            break

        transaction.append(team_votes)
        self.observations.append(transaction)
        self.tid += 1

    def eval(self, length=60000, burn=30):
        mcmc = mc.MCMC(self._build_model_list())
        mcmc.sample(length, burn)
        self.model = mcmc

    def eval_model_sans_players(self, length=40000, burn=0):
        mcmc = mc.MCMC(self._build_restricted_model_list())
        #mcmc.use_step_method(mc.DiscreteMetropolis, self.deck_var, proposal_distribution='Prior')
        mcmc.sample(length, burn, tune_throughout=False)

    def report(self):
        if self.model is None:
            self.eval()
        out = []
        for i in range(self.n_players):
            out.append(self.get_player_data(i))
        return out

    def get_player_data(self, i):
        out = {}
        role_key = "player_role_%d" % i
        side_key = "player_side_%d" % i

        temp_role = self._aggregate(list(self.model.trace(role_key)))
        out["role"] = {}
        for k, v in temp_role.iteritems():
            out["role"][self.player_array[int(k)][0]] = v
        out["side"] = self._aggregate(list(self.model.trace(side_key)))
        return out

    def _aggregate(self, l):
        out = dd(float)
        size = len(l) * 1.0
        for x in l:
            out[x] += 1 / size
        return dict(out)

    def print_report(self):
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.report())

    def _build_restricted_model_list(self):
        out = []
        out.append(self.deck_var)
        out.extend(self.player_side_vars[:])
        out.extend(self.player_role_vars[:])
        return out

    def _build_model_list(self):
        out = []
        out.append(self.deck_var)
        out.append(self.lady_will_duck)
        out.extend(self.player_side_vars[:])
        out.extend(self.player_role_vars[:])
        for duck in self.team_duck:
            out.append(duck)
        for player in self.players:
            out.extend(player.all_vars[:])
        flattened = [item for transaction in self.observations
                     for item in transaction]
        out.extend(flattened[:])
        return list(set(out))


base_game = DeceptionGame(ResistanceGame(5))
#base_game.add_known_role(0, "G1")
base_game.build_team([0, 1, 2], [1, 0, 1, 1, 0], 1)
base_game.team_and_successes([0, 1, 2], 2, 1, False)
#base_game.team_and_successes([0, 1, 2], 2, 2, False)
#base_game.player_sees_player_and_claims(0, 1, False)
#base_game.add_known_side(1, False)
base_game.eval()

base_game.print_report()
