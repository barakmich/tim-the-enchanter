def merlin_vote(game, player_id, team, votes, fail_req, r, deal):
    n_actually_good_people = sum(
        [int(game.player_is_good(deal, x)) for x in team])
    n_spies = len(team) - n_actually_good_people
    roles = [game.player_role(deal, x) for x in team]
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
            if game.merlin_ignorance.rand():
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


def mordred_vote(game, player_id, team, votes, fail_req, r, deal):
    n_actually_good_people = sum(
        [int(game.player_is_good(deal, x)) for x in team])
    n_spies = len(team) - n_actually_good_people
    roles = [game.player_role(deal, x) for x in team]
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
