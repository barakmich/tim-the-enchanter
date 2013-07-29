import pymc as mc
import functools
import itertools
from collections import defaultdict as dd
import pprint
import progressbar


def ResistanceGame(n_players):
  full_set = [("G1", True), ("G2", True), ("G3", True), ("E1", False), ("E2", False),
              ("G4", True), ("E3", False), ("G5", True), ("G6", True), ("E4", False)]
  return full_set[:n_players]


class DeceptionGame(object):
  def __init__(self, player_array):
    self.player_array = player_array
    self.all_permutations = list(itertools.permutations(player_array))
    self.n_players = len(player_array)
    self.trace = None
    self.observations = []
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
    self.tid += 1


  def eval(self, length=100):
    deck = self.all_permutations[:]
    new_deck = []
    trace = []
    progress = progressbar.ProgressBar(widgets=[": ", progressbar.Bar(marker=progressbar.RotatingMarker()), " ", progressbar.ETA()])
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
    if self.trace is None:
      self.eval()
    out = []
    for i in range(self.n_players):
      out.append(self.get_player_data(i))
    return out

  def get_player_data(self, i):
    out = {}
    out["role"] = dd(float)
    out["side"] = dd(float)

    cards = self._aggregate(self.trace, i)
    for k, v in cards.iteritems():
      role, side = k
      out["role"][role] += v
      out["side"][side] += v
    out["role"] = dict(out["role"])
    out["side"] = dict(out["side"])
    return out

  def _aggregate(self, l, i):
    out = dd(float)
    size = len(l) * 1.0
    for deal in l:
      out[deal[i]] += 1 / size
    return dict(out)


  def print_report(self):
    pp = pprint.PrettyPrinter(indent = 4)
    pp.pprint(self.report())


base_game = DeceptionGame(ResistanceGame(10))
#base_game.add_known_role(0, "G1")
#base_game.add_known_alliance(1, False)
base_game.player_sees_player_and_claims(0, 1, False)
#base_game.do_vote([1,2], [0,1,1,0,1], 1)
#base_game.do_mission([1,2], 0, False, 1)
#base_game.do_vote([0, 1, 2], [1,1,1,0,1], 2)
#base_game.do_mission([0, 1, 2], 1, False, 2)
#base_game.do_vote([3, 4], [0,0,1,1,1], 3)
#base_game.do_mission([3, 4], 0, False, 3)
#base_game.do_vote([3, 4], [0,0,1,1,1], 4)
#base_game.do_mission([0, 3, 4], 1, False, 4)
#base_game.do_vote([1, 3, 4], [0,1,1,0,1], 5)
#base_game.do_mission([1, 3, 4], 1, True, 5)
base_game.eval()

base_game.print_report()

