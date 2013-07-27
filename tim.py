import pymc as mc
import functools
import itertools
from collections import defaultdict as dd
import pprint


def ResistanceGame(n_players):
    full_set = [("G1", True), ("G2", True), ("G3", True),
                ("E1", False), ("E2", False), ("G4", True),
                ("E3", False), ("G5", True), ("G6", True), ("E4", False)]
    return full_set[:n_players]


class Player(object):
    def __init__(self, id, card, game, side):
        self.id_num = id
        self.role_str, _ = card
        self.game = game


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
            return self.role_side[role]

        def player_role(x, deck_var=self.deck_var):
            role_str = self.all_permutations[deck_var][x][0]
            return self.role_ids[role_str]

        for x in range(self.n_players):
            role = mc.Deterministic(eval=functools.partial(player_role, x),
                                    name="player_role_%d" % x,
                                    parents={"deck_var": self.deck_var},
                                    doc="Who is player %d?" % x,
                                    dtype=str,
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
            self.players.append(Player(x,
                                       player_array[x]))

        self.observations = []
        self.tid = 0

    def add_known_side(self, player_id, is_good):
        transaction = []
        obs = mc.Bernoulli("player_seen_tid%d" % self.tid,
                           self.player_side_vars[player_id],
                           value=is_good,
                           observed=True)
        transaction.append(obs)
        self.observations.append(transaction)
        self.tid += 1

    def add_known_role(self, player_id, role_str):
        transaction = []
        obs = mc.Bernoulli("player_seen_role_tid%d" % self.tid,
                           self.player_role_vars[player_id],
                           value=self.role_ids[role_str],
                           observed=True)
        transaction.append(obs)
        self.observations.append(transaction)
        self.tid += 1

    def eval(self, length=40000):
        mcmc = mc.MCMC(self._build_model_list())
        mcmc.sample(length, 2000)
        self.model = mcmc

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

    def _build_model_list(self):
        out = []
        out.append(self.deck_var)
        out.extend(self.player_side_vars[:])
        out.extend(self.player_role_vars[:])
        flattened = [item for transaction in self.observations
                     for item in transaction]
        out.extend(flattened[:])
        return list(set(out))


base_game = DeceptionGame(ResistanceGame(5))
base_game.eval(20000)
base_game.add_known_role(0, "G1")
base_game.add_known_side(1, False)
base_game.eval()

base_game.print_report()
