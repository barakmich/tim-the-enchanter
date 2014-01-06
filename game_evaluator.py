from collections import defaultdict as dd
import itertools
import progressbar
import random


def ResistanceGame(n_players):
    full_set = [("G", True), ("G", True), ("G", True),
                ("E", False), ("E", False), ("G", True),
                ("E", False), ("G", True), ("G", True), ("E", False)]
    return full_set[:n_players]


def AvalonGame(n_players):
    full_set = [("Merlin", True), ("G", True), ("G", True),
                ("E", False), ("ELance", False), ("GLance", True),
                ("Mordred", False), ("G", True), ("G", True),
                ("Oberon", False)]
    return full_set[:n_players]


class DeceptionGame(object):
    def __init__(self, player_array, model_class):
        self.player_array = player_array
        self.model = model_class(self)
        self.all_permutations = list(set(itertools.permutations(player_array)))
        self.quick_permutations = list(set(itertools.permutations(
            [("", p[1]) for p in player_array])))
        self.n_players = len(player_array)
        self.n_good = len([x for x in player_array if x[1] is True])
        self.trace = None
        self.observations = []
        self.seen = []
        self.tid = 0
        self.lancelots_switch_at = []

    def player_is_good(self, deal, player, round):
        if round is None:
            return deal[player][1]
        if self.player_role(deal, player) is not "GLance" and \
           self.player_role(deal, player) is not "ELance":
            return deal[player][1]
        if len(self.lancelots_switch_at) == 0:
            return deal[player][1]
        if len(self.lancelots_switch_at) == 1:
            if round >= self.lancelots_switch_at[0]:
                return not deal[player][1]
            else:
                return deal[player][1]
        if len(self.lancelots_switch_at) == 2:
            if round >= self.lancelots_switch_at[0] and \
               round < self.lancelots_switch_at[1]:
                return not deal[player][1]
            else:
                return deal[player][1]
        return deal[player][1]

    def player_role(self, deal, player):
        return deal[player][0]

    def add_known_alliance(self, player_id, is_good):
        transaction = []

        def obs(deal):
            if self.player_is_good(deal, player_id, None) == is_good:
                return True
            else:
                return None
        transaction.append(obs)
        self.observations.append(transaction)
        self.seen.append({"type": "known_side",
                          "player": player_id,
                          "is good": is_good,
                          "print_order": ["player",
                                          "is good"]})
        self.tid += 1

    def switch_lancelots(self, round):
        transaction = []
        rnd = round - 1

        def obs(deal):
            return True

        self.lancelots_switch_at.append(rnd)

        transaction.append(obs)
        self.observations.append(transaction)
        self.seen.append({"type": "switch",
                          "round": rnd,
                          "print_order": ["round"]})
        self.tid += 1

    def add_known_role(self, player_id, role_str):
        transaction = []

        def obs(deal):
            if self.player_role(deal, player_id) == role_str:
                return True
            else:
                return None
        transaction.append(obs)
        self.observations.append(transaction)
        self.seen.append({"type": "known_role",
                          "player": player_id,
                          "role": role_str,
                          "print_order": ["player",
                                          "role"]})
        self.tid += 1

    def player_sees_player_and_claims(self, p1, p2, claim, round):
        transaction = []
        rnd = round - 1

        def obs(deal):
            self.model.set_deal(deal)
            return self.model.player_sees_player_and_claims(p1, p2, claim, rnd)
        transaction.append(obs)
        self.observations.append(transaction)
        self.seen.append({"type": "lady",
                          "p1": p1,
                          "p2": p2,
                          "is good": claim,
                          "round": round,
                          "print_order": ["p1",
                                          "p2",
                                          "round",
                                          "is good"]})
        self.tid += 1

    def do_mission(self, team, fails, must_fail, r):
        transaction = []
        rnd = r - 1

        def obs(deal):
            self.model.set_deal(deal)
            return self.model.mission(team, fails, must_fail, rnd)

        transaction.append(obs)
        self.observations.append(transaction)
        self.seen.append({"type": "mission",
                          "team": team,
                          "fails": fails,
                          "round": r,
                          "must fail": must_fail,
                          "print_order": ["team",
                                          "fails",
                                          "must fail",
                                          "round"]})
        self.tid += 1

    def do_vote(self, team, votes, fail_req, r):
        transaction = []
        rnd = r - 1

        def obs(deal):
            self.model.set_deal(deal)
            return self.model.votes(team, votes, fail_req, rnd)

        transaction.append(obs)
        self.observations.append(transaction)
        self.seen.append({"type": "vote",
                          "team": team,
                          "votes": votes,
                          "round": r,
                          "fails required": fail_req,
                          "print_order": ["team", "votes", "round"]})
        self.tid += 1

    def load_save(self, input_list):
        for statement in input_list:
            type = statement["type"]
            if type == "vote":
                self.do_vote(statement["team"],
                             statement["votes"],
                             statement["fails required"],
                             statement["round"])
            if type == "switch":
                self.switch_lancelots(statement["round"])
            elif type == "mission":
                self.do_mission(statement["team"],
                                statement["fails"],
                                statement["must fail"],
                                statement["round"])
            elif type == "lady":
                self.player_sees_player_and_claims(statement["p1"],
                                                   statement["p2"],
                                                   statement["is good"],
                                                   statement.get("round", -1))
            elif type == "known_side":
                self.add_known_alliance(statement["player"],
                                        statement["is good"])
            elif type == "known_role":
                self.add_known_role(statement["player"],
                                    statement["role"])

    def eval(self, length=10, quick=False):
        random.seed()
        if quick:
            deck = self.quick_permutations[:]
        else:
            deck = self.all_permutations[:]
        new_deck = []
        trace = {}
        progress = progressbar.ProgressBar(
            widgets=["Simulating games: ",
                     progressbar.Bar(marker="*"),
                     " ", progressbar.ETA()])
        for i in progress(range(length)):
            falses = 0
            trues = 0
            nones = 0
            for deal in deck:
                f_list = []
                for obs in self.observations:
                    for tid in obs:
                        f_list.append(tid)
                is_bad = False
                dont_copy = False
                for f in f_list:
                    out = f(deal)
                    if out is None:
                        is_bad = True
                        dont_copy = True
                        nones += 1
                        break
                    if out is True:
                        trues += 1
                        continue
                    if out is False:
                        is_bad = True
                        falses += 1
                        break
                if not is_bad:
                    if deal not in trace:
                        trace[deal] = 1
                    trace[deal] += 1
                if not dont_copy:
                    new_deck.append(deal)
            deck = new_deck
            new_deck = []

        self.trace = trace

    def report(self):
        return self.get_player_data()

    def get_player_data(self):
        out = []
        for i in range(self.n_players):
            out.append({})
            out[i]["role"] = dd(float)
            out[i]["side"] = dd(float)

        size = sum(self.trace.values()) * 1.0
        for deal, score in self.trace.items():
            for i, card in enumerate(deal):
                role, side = card
                out[i]["role"][role] += (score * 1.0) / size
                out[i]["side"][side] += (score * 1.0) / size
        for i in range(self.n_players):
            out[i]["role"] = dict(out[i]["role"])
            out[i]["side"] = dict(out[i]["side"])
        return out

    def _aggregate(self, l, i):
        out = dd(float)
        size = len(l) * 1.0
        for deal in l:
            out[deal[i]] += 1 / size
        return dict(out)

    def __str__(self):
        return "%d Player Game (%d constraints)" % (self.n_players,
                                                    len(self.seen))

    def disbelieve(self, i):
        self.observations = self.observations[:i] + self.observations[i + 1:]
        self.seen = self.seen[:i] + self.seen[i + 1:]
        self.trace = {}
