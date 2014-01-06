import os
import readline
import sys
import colorama
import json
from colorama import Fore, Style

from models.default_model import DefaultModel
from game_evaluator import DeceptionGame, AvalonGame



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
        has_roles = True
        for score, role in roles:
            if role == "":
                has_roles = False
                break
            row += "%2.1f%% %s " % (
                score * 100, role)
        if has_roles:
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


def help():
    print(Fore.GREEN + "Initial Commands:")
    print("load <filename> -- Loads a savefile")
    print("newgame -- Starts a new game")
    print("\n")
    print(Fore.GREEN + "Game Commands:")
    print("save <filename> -- Saves a game to file")
    print("ls -- Lists current assertions")
    print("disb <index> -- Delete (disbelieve) an assertion")
    print("name -- Name a player index for pretty printing")
    print("side -- Assert that someone must be good or evil")
    print("lady -- Assert that one player saw another and made a claim")
    print("vote -- Assert a voted-on team and the votes"
          " (whether it succeeded or not)")
    print("switch -- Good and Evil Lancelots switch")
    print("mission -- Assert the results of a team and a mission")
    print("eval <repetitions> -- Quick eval, discounting special roles")
    print("fulleval <repetitions> -- Eval, counting special roles")
    print("report -- Show last report again")


def main():
    colorama.init(autoreset=True)
    readline.get_history_length()
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
            if command == "help":
                    help()
                    continue
            if game is None:
                if command == "newgame":
                    nplayers = raw_input("How many players? ")
                    game = DeceptionGame(
                        AvalonGame(int(nplayers)), DefaultModel)
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
                            AvalonGame(int(metadata["game_size"])),
                            DefaultModel)
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
                game.trace = {}
                continue

            elif command == "mission":
                team = [int(x) for x in raw_input("Team? ").strip()]
                fails = int(raw_input("# of Fails? ").strip())
                must = int(raw_input("Spys must fail? ").strip()) == 1
                round = int(raw_input("Round? ").strip())
                game.do_mission(team, fails, must, round)
                game.trace = {}
                continue

            elif command == "lady" or command == "lol":
                p1 = int(raw_input("ID For Lady? ").strip())
                p2 = int(raw_input("ID For Target? ").strip())
                claim = int(raw_input("Claim? ").strip()) == 1
                round = int(raw_input("Round? ").strip()) == 1
                game.player_sees_player_and_claims(p1, p2, claim, round)
                game.trace = {}
                continue

            elif command == "side":
                p1 = int(raw_input("ID For Assertion? ").strip())
                claim = int(raw_input("Good? ").strip()) == 1
                game.add_known_alliance(p1, claim)
                game.trace = {}
                continue

            elif command == "switch":
                r = int(raw_input("Starting in round?").strip())
                game.switch_lancelots(r)
                game.trace = {}
                continue

            elif command == "eval":
                times = 200 / (game.n_players - 4) * 2
                if len(command_list) > 1:
                    times = int(command_list[1])
                game.eval(times, quick=True)
                repl_report(game.report(), namemap, game.n_good)
            elif command == "fulleval":
                times = 200 / (game.n_players - 4) * 2
                if len(command_list) > 1:
                    times = int(command_list[1])
                game.eval(times)
                repl_report(game.report(), namemap, game.n_good)
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
        except EOFError:
            print "Canceled"
            continue
        except Exception, e:
            print str(e)
            continue


if __name__ == '__main__':
    main()
