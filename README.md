# Tim the Enchanter
#### _There are some who call me.... Tim._

It will occur to anyone who plays enough [Resistance](http://boardgamegeek.com/boardgame/41114/the-resistance) or [Avalon](http://boardgamegeek.com/boardgame/128882/the-resistance-avalon) that there's a great deal of probability afoot. If you've ever said "There's a 50/50 chance this team is bad!" you know what I'm talking about.

Tim the Enchanter is a tool to track these games, build a (very simplistic) Bayesian model of the situation as it stands, and, hopefully, deduce exactly what everyone's role is.
In the future, it may also turn into a full-blown AI.

Written in Python (fortunately thematic!).

#### _So how did you become king, then?_

```
git clone https://github.com/barakmich/tim-the-enchanter.git
cd tim-the-enchanter
pip install -r requirements.txt
python tim.py
```

That'll get you going. I highly recommend you also create a virtualenv using [virtualenvwrapper](http://virtualenvwrapper.readthedocs.org/en/latest/) so that you don't muck with your system install of Python.

You may notice it's slow on 10-player games. For this, I recommend using pypy; tim-the-enchanter is compatible with pypy v1.9 and higher, which is convienent for Ubuntu users, who can simply 
```
apt-get install pypy
pypy tim.py
```

Or likewise, choose pypy for their virtualenv.

#### _If she weighs the same as a duck, she's made of wood. And therefore..... a witch!_

So you're running tim.py. Now what?

```
help
```

Can give you a list of commands. Most commands ask followup questions. Until I get a better parse going, you'll have to work in binary and give the players at your table numbers, 0-9. Here's an example exchange:

```
Tim the Enchanter v1.0
None> newgame
How many players? 5
5 Player Game (0 constraints)> vote
Team? 12
Votes? 10000
Round? 1
# Fails Required? 1
5 Player Game (1 constraints)> eval 300000
Simulating games: |*********************************************************| Time: 0:00:08
 (4): 60.861300% Good 39.138700% Evil
 (3): 60.839685% Good 39.160315% Evil
 (1): 59.810877% Good 40.189123% Evil
 (2): 59.801591% Good 40.198409% Evil
 (0): 58.686548% Good 41.313452% Evil
5 Player Game (1 constraints)> 
```

We started a new game, and player zero voted for a team that everyone else hated and he wasn't on. That makes him look a little evil (and casts a little suspicion on 1 and 2, who were on the team). But not too much -- it's only round one. Suppose he had done that on round 5 instead?

```
5 Player Game (1 constraints)> ls    
0: Vote -- Team: [1, 2] Votes: [1, 0, 0, 0, 0] Round: 1 
5 Player Game (1 constraints)> disb 0
5 Player Game (0 constraints)> vote
Team? 12
Votes? 10000
Round? 5
# Fails Required? 1
5 Player Game (1 constraints)> eval 300000
Simulating games: |********************************************************| Time: 0:00:04
 (4): 66.937259% Good 33.062741% Evil
 (3): 66.898706% Good 33.101294% Evil
 (1): 61.507670% Good 38.492330% Evil
 (2): 61.462866% Good 38.537134% Evil
 (0): 43.193499% Good 56.806501% Evil
```

More clearly evil, just from that one vote. In concert with the other assertions, the possibilities will help bring the truly evil to light.

####  _"You know much that is hidden, oh Tim." "Quite."_

Feel free to help me improve it. Do drop me a line, or [follow me on Twitter](http://twitter.com/barakmich). 
Special thanks to [Nyeek game nights](http://www.meetup.com/NyeekGames/) where I've been known to field test this! If you're in NYC, come visit!
