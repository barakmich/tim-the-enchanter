import pymc as mc
import functools
import itertools
from collections import defaultdict as dd
import pprint
import progressbar
import readline
import sys
from clint.textui import colored, puts


def ResistanceGame(n_players):
  full_set = [("G1", True), ("G2", True), ("G3", True), ("E1", False), ("E2", False),
              ("G4", True), ("E3", False), ("G5", True), ("G6", True), ("E4", False)]
  return full_set[:n_players]


class DeceptionGame(object):
  def __init__(self, player_array):
    self.player_array = player_array
    self.all_permutations = list(itertools.permutations(player_array))
    self.n_players = len(player_array)
    self.n_good = len([x for x in player_array if x[1] == True])
    self.trace = None
    self.observations = []
    self.seen = []
    self.tid = 0
    self.lady_will_duck = mc.Bernoulli("lady_will_duck", 0.5)
    self.mission_ducks_on_round = [None] * 5
    self.mission_ducks_on_round[0] = mc.Bernoulli("missionduck_on_0", 0.5)
    self.mission_ducks_on_round[1] = mc.Bernoulli("missionduck_on_1", 0.5)
    self.mission_ducks_on_round[2] = mc.Bernoulli("missionduck_on_2", 0.5)
    self.mission_ducks_on_round[3] = mc.Bernoulli("missionduck_on_3", 0.0)
    self.mission_ducks_on_round[4] = mc.Bernoulli("missionduck_on_4", 0.0)
    self.ignorance_on_round = [None] * 5
    self.ignorance_on_round[0] = mc.Bernoulli("ignorance_on_0", 0.9)
    self.ignorance_on_round[1] = mc.Bernoulli("ignorance_on_1", 0.7)
    self.ignorance_on_round[2] = mc.Bernoulli("ignorance_on_2", 0.5)
    self.ignorance_on_round[3] = mc.Bernoulli("ignorance_on_3", 0.3)
    self.ignorance_on_round[4] = mc.Bernoulli("ignorance_on_4", 0.3)

  def player_is_good(self, deal, player):
    return deal[player][1]

  def player_is_role(self, deal, player):
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
    self.seen.append(["Known role ", player_id, "Good" if is_good else "Evil"])
    self.tid += 1

  def add_known_role(self, player_id, role_str):
    transaction = []
    def obs(deal):
      if self.player_is_role(deal, player_id) == role_str:
        return True
      else:
        return None
    transaction.append(obs)
    self.observations.append(transaction)
    self.seen.append(["Known role ", player_id, role_str])
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
    self.seen.append(["Lady:", p1, "says", p2 , "is", "Good" if claim else "Evil"])
    self.tid += 1

  def do_mission(self, team, fails, must_fail, r):
    transaction = []
    rnd = r - 1
    def obs(deal):
      n_actually_good_people = sum([int(self.player_is_good(deal, x)) for x in team])
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
    self.seen.append(["Mission:"] + team + ["with %d fails on round %d" % (fails, r)])
    self.tid += 1

  def do_vote(self, team, votes, r):
    transaction = []
    rnd = r - 1
    def obs(deal):
      n_actually_good_people = sum([int(self.player_is_good(deal, x)) for x in team])
      n_spies = len(team) - n_actually_good_people
      could_happen = True
      for player, vote in enumerate(votes):
        if self.player_is_good(deal, player):
          if player in team:
            continue
          elif n_spies > 0:
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
          if player in team:
            continue
          elif n_spies == 0:
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
    self.seen.append(["Vote:"] + team + ["voted %s round %d" % (votes, r)])
    self.tid += 1


  def eval(self, length=10):
    deck = self.all_permutations[:]
    new_deck = []
    trace = []
    progress = progressbar.ProgressBar(widgets=["Simulating games: ", progressbar.Bar(marker="*"), " ", progressbar.ETA()])
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

    progress = progressbar.ProgressBar(widgets=["Reticulating splines: ", progressbar.Bar(marker="*"), " ", progressbar.ETA()])
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
    return "%d Player Game (%d constraints)" % (self.n_players, len(self.seen))

  def disbelieve(self, i):
    self.observations = self.observations[:i] + self.observations[i + 1:]
    self.seen = self.seen[:i] + self.seen[i + 1:]
    self.trace = []

  def print_report(self):
    pp = pprint.PrettyPrinter(indent = 4)
    pp.pprint(self.report())

def repl_report(report, namemap, ngood):
  sort_order = sorted([(report[i]["side"].get(True, 0.0), i) for i in range(len(report))], reverse=True)

  still_good = 0
  for goodness, i in sort_order:
    row = "%s: %2f%% Good %2f%% Evil" % (namemap.get(i, "") + "(%s)" % str(i), goodness * 100, (1.0 - goodness) * 100)
    if still_good < ngood:
      puts(colored.cyan(row))
    else:
      puts(colored.red(row))
    still_good += 1


def main():
  puts(colored.green("Welcome to Tim the Enchanter v1.0"))

  game = None
  namemap = {}

  while True:
    command_str = raw_input("%s> " % game)
    command_list = command_str.strip().split(" ")
    command = command_list[0]
    if command == "quit" or command == "q" or command == "exit":
      sys.exit(0)
    if (command != "newgame" and command != "testgame") and game is None:
      puts(colored.red("Need to create a game"))
      continue
    elif command == "newgame":
      nplayers = raw_input("How many players? ")
      game = DeceptionGame(ResistanceGame(int(nplayers)))
      namemap = {}
      continue
    elif command == "testgame":
      game = DeceptionGame(ResistanceGame(5))
      game.do_vote([1,2], [0,1,1,0,1], 1)
      game.do_mission([1,2], 0, False, 1)
      game.do_vote([0, 1, 2], [1,1,1,0,1], 2)
      game.do_mission([0, 1, 2], 1, False, 2)
      game.do_vote([3, 4], [0,0,1,1,1], 3)
      game.do_mission([3, 4], 0, False, 3)
      game.do_vote([3, 4], [0,0,1,1,1], 4)
      game.do_mission([0, 3, 4], 1, False, 4)
      namemap = {}
      continue
    elif command == "ls":
      for i, statement in enumerate(game.seen):
        name = " ".join([namemap.get(x, str(x)) for x in statement])
        print "%d: %s" % (i, name)
      continue
    elif command == "vote":
      team = [int(x) for x in raw_input("Team? ").strip().split(" ")]
      votes = [int(x) for x in raw_input("Votes? ").strip().split(" ")]
      round = int(raw_input("Round? ").strip())
      game.do_vote(team, votes, round)
      game.trace = []
      continue

    elif command == "mission":
      team = [int(x) for x in raw_input("Team? ").strip().split(" ")]
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
    elif command == "report":
      repl_report(game.report(), namemap, game.n_good)
    elif command == "name":
      if len(command_list) < 3:
        puts(colored.red("No args?"))
        continue
      namemap[int(command_list[1])] = command_list[2]
    elif command == "disb" or command == "disbelieve":
      if len(command_list) < 2:
        puts(colored.red("No args?"))
        continue
      game.disbelieve(int(command_list[1]))
    else:
      puts(colored.red("Unknown command: %s" % command))
      continue






if __name__ == '__main__':
  main()
base_game = DeceptionGame(ResistanceGame(5))
#base_game.add_known_role(0, "G1")
#base_game.add_known_alliance(1, False)
#base_game.player_sees_player_and_claims(0, 1, True)
#base_game.player_sees_player_and_claims(1, 2, False)
#base_game.player_sees_player_and_claims(2, 3, False)
base_game.do_vote([1,2], [0,1,1,0,1], 1)
base_game.do_mission([1,2], 0, False, 1)
base_game.do_vote([0, 1, 2], [1,1,1,0,1], 2)
base_game.do_mission([0, 1, 2], 1, False, 2)
base_game.do_vote([3, 4], [0,0,1,1,1], 3)
base_game.do_mission([3, 4], 0, False, 3)
base_game.do_vote([3, 4], [0,0,1,1,1], 4)
base_game.do_mission([0, 3, 4], 1, False, 4)
#base_game.do_vote([1, 3, 4], [0,1,1,0,1], 5)
#base_game.do_mission([1, 3, 4], 1, True, 5)
base_game.eval(100)

base_game.print_report()

