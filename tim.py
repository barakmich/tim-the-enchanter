import pymc as mc
import functools
import itertools
from collections import defaultdict as dd
import pprint
import numpy
from numpy.random import random


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
                         trace=False,
                         size=n_players)
        matrix.append(vec)
        all_vars.append(vec)

    # Enforce that there's only one role for each player.
    for i, player_vec in enumerate(matrix):
        det_var = sum(vec)
        all_vars.append(det_var)
        obs = mc.Bernoulli(
            "player_%d_one_role_constraint_%d" % (id, i),
            det_var,
            value=1.0,
            trace=False,
            observed=True)
        all_vars.append(obs)

    # Enforce that there's only one player per role.
    for i in range(n_players):
        det_var = sum([vec[i] for vec in matrix])
        all_vars.append(det_var)
        obs = mc.Bernoulli(
            "player_%d_one_player_constraint_%d" % (id, i),
            det_var,
            value=1.0,
            trace=False,
            observed=True)
        all_vars.append(obs)
    return matrix, all_vars

class Player(object):
    ''' Representing all that the player is and knows '''
    def __init__(self, id, game, side_var, role_var):
        self.id = id
        self.game = game
        self.side_var = side_var
        self.role_var = role_var
        self.all_vars = []
        self.build_belief_matrix()

    def side(self):
        return self.side_var

    def role(self):
        return self.role_var

    def build_belief_matrix(self):
        self.matrix = []
        self.matrix, self.all_vars = \
            BuildNbyNBeliefMatrix(self.id, self.game.n_players)

        # Enforce that the player completely knows her own role.
        def player_knows_self(self_role=self.role_var):
            return self.matrix[self.id][self_role]

        knows = mc.Deterministic(eval=player_knows_self,
                                 name="player_knows_self_%d" % self.id,
                                 parents={"self_role": self.role_var},
                                 doc="Player knows self %d" % self.id,
                                 dtype=float,
                                 trace=True,
                                 plot=False)
        self.all_vars.append(knows)
        obs = mc.Bernoulli(
            "player_knows_self_constraint_%d" % self.id,
            knows,
            value=1.0,
            observed=True)
        self.all_vars.append(obs)

        # Convenience vars for trust
        self.side_belief = []

        def side_belief(player_id, role_vec):
            out = 0.0
            for i, role in enumerate(role_vec):
                if self.game.role_id_is_good(i):
                    out += role
            out = out / len(role_vec)
            return out

        for i in range(self.game.n_players):
            is_good = mc.Deterministic(eval=functools.partial(side_belief, i),
                                       name="player%d_trust_%d" % (self.id, i),
                                       parents={"role_vec": self.matrix[i]},
                                       doc="Does player trust %d?" % i,
                                       dtype=float,
                                       trace=True,
                                       plot=False)
            self.side_belief.append(is_good)
            self.all_vars.append(is_good)

    def get_good_belief_for(self, player_id):
        return self.side_belief[player_id]

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
            self.players.append(Player(x, self, side, role))

        for x in range(50000):
            self.deck_var.random()

        self.observations = []
        self.tid = 0

    def get_role_id_for(self, name):
        return self.role_ids[name]

    def role_id_is_good(self, role_id):
        return self.role_side[role_id]

    def add_known_side(self, player_id, is_good):
        transaction = []

        def player_is_good(side_var):
            if side_var == is_good:
                return 1.0
            return 0.0

        det = mc.Deterministic(
            eval=player_is_good,
            name="player_seen_det_tid%d" % self.tid,
            parents={"side_var": self.player_side_vars[player_id]},
            doc="Det TID%d" % self.tid,
            dtype=float,
            trace=False,
            plot=False)

        transaction.append(det)

        obs = mc.Degenerate("player_seen_tid%d" % self.tid,
                            det,
                            value=1.0,
                            observed=True)
        transaction.append(obs)
        self.observations.append(transaction)
        self.tid += 1

    def add_known_role(self, player_id, role_str):
        transaction = []
        known_role_id = self.get_role_id_for(role_str)

        def bool_stoch_logp(value, in_val):
            if value == in_val:
                return -numpy.log(1)
            else:
                return -numpy.inf

        def bool_stoch_rand(in_val):
            return bool(numpy.round(random()))

        def is_known_role(role_id):
            if role_id == known_role_id:
                return True
            return False

        det = mc.Deterministic(
            eval=is_known_role,
            name="player_seen_role_det_tid%d" % self.tid,
            parents={"role_id": self.player_role_vars[player_id]},
            doc="Det TID%d" % self.tid,
            dtype=bool,
            trace=True,
            plot=False)

        transaction.append(det)

        obs = mc.Stochastic(
            logp=bool_stoch_logp,
            doc="Boolean stochastic observation",
            name="player_seen_role_tid%d" % self.tid,
            parents={"in_val": det},
            random=bool_stoch_rand,
            trace=True,
            value=True,
            dtype=bool,
            observed=True,
            cache_depth=2,
            plot=False,
            verbose=0)

        #obs = mc.Uniform("player_seen_role_tid%d" % self.tid,
                                 #0, det,
                                 #value=1,
                                 #observed=True)
        transaction.append(obs)
        self.observations.append(transaction)
        self.tid += 1

    def eval(self, length=40000, burn=10000):
        mcmc = mc.MCMC(self._build_model_list())
        mcmc.sample(length, burn)
        self.model = mcmc

    def eval_model_sans_players(self, length=40000, burn=500):
        mcmc = mc.MCMC(self._build_restricted_model_list())
        mcmc.sample(length, burn)

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
        out.extend(self.player_side_vars[:])
        out.extend(self.player_role_vars[:])
        for player in self.players:
            out.extend(player.all_vars[:])
        flattened = [item for transaction in self.observations
                     for item in transaction]
        out.extend(flattened[:])
        return list(set(out))


base_game = DeceptionGame(ResistanceGame(10))
base_game.eval_model_sans_players()
base_game.add_known_role(0, "G1")
base_game.add_known_side(1, False)
base_game.eval()

base_game.print_report()
