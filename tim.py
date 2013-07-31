import itertools
from collections import defaultdict as dd
import pprint
import progressbar
import os
import readline
import random
import sys
import colorama
import json
from colorama import Fore, Style


def ResistanceGame(n_players):
    full_set = [("G1", True), ("G2", True), ("G3", True),
                ("E1", False), ("E2", False), ("G4", True),
                ("E3", False), ("G5", True), ("G6", True), ("E4", False)]
    return full_set[:n_players]


def AvalonGame(n_players):
    full_set = [("Merlin", True), ("G2", True), ("G3", True),
                ("E1", False), ("E2", False), ("G4", True),
                ("E3", False), ("G5", True), ("G6", True), ("E4", False)]
    return full_set[:n_players]


class Bernoulli(object):
    def __init__(self, percentage):
        self.percentage = percentage

    def rand(self):
        return random.random() < self.percentage

    def random(self):
        return self.rand()


class DeceptionGame(object):
    def __init__(self, player_array):
        self.player_array = player_array
        self.all_permutations = list(itertools.permutations(player_array))
        self.n_players = len(player_array)
        self.n_good = len([x for x in player_array if x[1] is True])
        self.trace = None
        self.observations = []
        self.seen = []
        self.tid = 0
        self.lady_will_duck = Bernoulli(0.5)
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

    def player_is_good(self, deal, player):
        return deal[player][1]

    def player_role(self, deal, player):
        return deal[player][0]

    def add_known_alliance(self, player_id, is_good):
        transaction = []

        def obs(deal):
            if self.player_is_good(deal, player_id) == is_good:
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

    def player_sees_player_and_claims(self, p1, p2, claim):
        transaction = []

        def obs(deal):
            if self.player_is_good(deal, p1):
                if self.player_is_good(deal, p2) == claim:
                    return True
                else:
                    return None
            else:
                if self.lady_will_duck.rand():
                    if self.player_is_good(deal, p2) == claim:
                        return True
                    else:
                        return False
                else:
                    if self.player_is_good(deal, p2) == claim:
                        return False
                    else:
                        return True
        transaction.append(obs)
        self.observations.append(transaction)
        self.seen.append({"type": "lady",
                          "p1": p1,
                          "p2": p2,
                          "is good": claim,
                          "print_order": ["p1",
                                          "p2",
                                          "is good"]})
        self.tid += 1

    def do_mission(self, team, fails, must_fail, r):
        transaction = []
        rnd = r - 1

        def obs(deal):
            n_actually_good_people = sum(
                [int(self.player_is_good(deal, x)) for x in team])
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
            n_actually_good_people = sum(
                [int(self.player_is_good(deal, x)) for x in team])
            n_spies = len(team) - n_actually_good_people
            could_happen = True
            for player, vote in enumerate(votes):
                if player in team:
                    continue
                elif self.player_is_good(deal, player):
                    if n_spies > fail_req - 1:
                        if self.player_role(deal, player) == "Merlin":
                            continue
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
            elif type == "mission":
                self.do_mission(statement["team"],
                                statement["fails"],
                                statement["must fail"],
                                statement["round"])
            elif type == "lady":
                self.player_sees_player_and_claims(statement["p1"],
                                                   statement["p2"],
                                                   statement["is good"])
            elif type == "known_side":
                self.add_known_alliance(statement["player"],
                                        statement["is good"])
            elif type == "known_role":
                self.add_known_role(statement["player"],
                                    statement["role"])

    def eval(self, length=10, with_merlin=False):
        random.seed()
        if not with_merlin:
            deck = self.all_permutations[:]
        else:
            deck = list(itertools.permutations(AvalonGame(self.n_players)))
        new_deck = []
        trace = []
        progress = progressbar.ProgressBar(
            widgets=["Simulating games: ",
                     progressbar.Bar(marker="*"),
                     " ", progressbar.ETA()])
        for i in progress(range(length)):
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
                        break
                    if out is True:
                        continue
                    if out is False:
                        is_bad = True
                        continue

                if not is_bad:
                    trace.append(deal)
                if not dont_copy:
                    new_deck.append(deal)
            deck = new_deck
            new_deck = []

        self.trace = trace

    def report(self):
        if self.trace == []:
            self.eval()
        return self.get_player_data()

    def get_player_data(self):
        out = []
        for i in range(self.n_players):
            out.append({})
            out[i]["role"] = dd(float)
            out[i]["side"] = dd(float)

        progress = progressbar.ProgressBar(
            widgets=["Reticulating splines: ",
                     progressbar.Bar(marker="*"),
                     " ", progressbar.ETA()])
        size = len(self.trace) * 1.0
        for deal in progress(self.trace):
            for i, card in enumerate(deal):
                role, side = card
                out[i]["role"][role] += 1.0 / size
                out[i]["side"][side] += 1.0 / size
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
        self.trace = []

    def print_report(self):
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.report())


def repl_report(report, namemap, ngood):
    sort_order = sorted(
        [(report[i]["side"].get(True, 0.0), i)
         for i in range(len(report))],
        reverse=True)

    still_good = 0
    for goodness, i in sort_order:
        row = "%s: %2f%% Good %2f%% Evil" % (
            namemap.get(i, "") + " (%s)" % str(i),
            goodness * 100,
            (1.0 - goodness) * 100)
        if still_good < ngood:
            print(Fore.CYAN + Style.BRIGHT + row)
        else:
            print(Fore.RED + Style.BRIGHT + row)
        roles = sorted([(v, k) for k, v in report[i]["role"].iteritems()],
                       reverse=True)
        row = "    "
        for score, role in roles:
            row += "%2.1f%% %s " % (
                score * 100, role)
        print(row)

        still_good += 1


def display_statement(statement, namemap):
    out = ""
    out += Fore.MAGENTA + Style.BRIGHT
    out += statement["type"].title()
    out += Style.RESET_ALL + " -- "
    for key in statement["print_order"]:
        out += Fore.YELLOW
        out += key.title() + ": "
        out += Style.RESET_ALL
        out += str(statement[key]).title() + " "
    return out


def main():
    colorama.init(autoreset=True)
    print(Fore.GREEN + Style.BRIGHT + "Tim the Enchanter v1.0")

    game = None
    namemap = {}

    while True:
        try:
            command_str = raw_input("%s> " % game)
            command_list = command_str.strip().split(" ")
            command = command_list[0]
            if command == "quit" or command == "q" or command == "exit":
                sys.exit(0)
            if game is None:
                if command == "newgame":
                    nplayers = raw_input("How many players? ")
                    game = DeceptionGame(ResistanceGame(int(nplayers)))
                    namemap = {}
                elif command == "load":
                    if len(command_list) < 2:
                        print(Fore.RED + "Need an input file")
                        continue
                    inpath = os.path.expanduser(command_list[1])
                    with open(inpath, "r") as savefile:
                        observations = json.load(savefile)
                        metadata = observations[0]
                        data = observations[1:]

                        game = DeceptionGame(
                            ResistanceGame(int(metadata["game_size"])))
                        namemap = metadata["player_names"]
                        game.load_save(data)
                else:
                    print(Fore.RED + "Need to create a game")
                continue
            elif command == "ls":
                for i, statement in enumerate(game.seen):
                    print "%d: %s" % (i, display_statement(statement, namemap))
                continue
            elif command == "vote":
                input = raw_input("Team? ").strip()
                team = [int(x) for x in input]
                votes = [int(x) for x in raw_input("Votes? ").strip()]
                round = int(raw_input("Round? ").strip())
                fail_req = int(raw_input("# Fails Required? ").strip())
                game.do_vote(team, votes, fail_req, round)
                game.trace = []
                continue

            elif command == "mission":
                team = [int(x) for x in raw_input("Team? ").strip()]
                fails = int(raw_input("# of Fails? ").strip())
                must = int(raw_input("Spys must fail? ").strip()) == 1
                round = int(raw_input("Round? ").strip())
                game.do_mission(team, fails, must, round)
                game.trace = []
                continue

            elif command == "lady" or command == "lol":
                p1 = int(raw_input("ID For Lady? ").strip())
                p2 = int(raw_input("ID For Target? ").strip())
                claim = int(raw_input("Claim? ").strip()) == 1
                game.player_sees_player_and_claims(p1, p2, claim)
                game.trace = []
                continue

            elif command == "side":
                p1 = int(raw_input("ID For Assertion? ").strip())
                claim = int(raw_input("Good? ").strip()) == 1
                game.add_known_alliance(p1, claim)
                game.trace = []
                continue

            elif command == "eval":
                times = 200 / (game.n_players - 4) * 2
                if len(command_list) > 1:
                    times = int(command_list[1])
                game.eval(times)
            elif command == "merlineval":
                times = 200 / (game.n_players - 4) * 2
                if len(command_list) > 1:
                    times = int(command_list[1])
                game.eval(times, with_merlin=True)
            elif command == "report":
                repl_report(game.report(), namemap, game.n_good)
            elif command == "save":
                if len(command_list) < 2:
                    print(Fore.RED + "Need an output file")
                    continue
                metadata = [{
                    "game_size": game.n_players,
                    "player_names": namemap
                }]
                outpath = os.path.expanduser(command_list[1])
                with open(outpath, "w") as savefile:
                    json.dump(metadata + game.seen, savefile, indent=2)
            elif command == "name":
                if len(command_list) < 3:
                    print(Fore.RED + "No args?")
                    continue
                namemap[int(command_list[1])] = command_list[2]
            elif command == "disb" or command == "disbelieve":
                if len(command_list) < 2:
                    print(Fore.RED + "No args?")
                    continue
                game.disbelieve(int(command_list[1]))
            else:
                print(Fore.RED + "Unknown command: %s" % command)
                continue
        except Exception, e:
            print str(e)
            continue


if __name__ == '__main__':
    main()
