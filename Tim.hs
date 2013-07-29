{-# LANGUAGE NoMonomorphismRestriction #-}
{-# LANGUAGE ConstraintKinds #-}
{-# LANGUAGE DoAndIfThenElse #-}

import qualified Numeric.Probability.Distribution as Dist
import Numeric.Probability.Distribution as Probs
--import Control.Monad (liftM2, replicateM, ap)
--import Control.Monad (ap)
import Control.Monad.Parallel (replicateM)
import Control.Monad (replicateM, ap)
import Data.List (permutations, isPrefixOf)
import Data.List.Split (splitOn)
import qualified Numeric.Probability.Random as Rnd
import Numeric.Probability.Trace (Trace)

type Prob = Double
type Dist a = Dist.T Prob a

data Side = Good | Evil
  deriving (Show, Eq, Ord)

otherSide Good = Evil
otherSide Evil = Good

data Role = Role { roleName :: String 
                 , roleSide :: Side }
  deriving (Show, Eq, Ord)

type Deal = [Role]

good1 = Role "G1" Good
good2 = Role "G2" Good
good3 = Role "G3" Good
good4 = Role "G4" Good
good5 = Role "G5" Good
good6 = Role "G6" Good
bad1 = Role "E1" Evil
bad2 = Role "E2" Evil
bad3 = Role "E3" Evil
bad4 = Role "E4" Evil

defaultGame :: Deal
defaultGame = [good1, good2, good3, bad1, bad2, 
               good4, bad3, good5, good6, bad4 ]

gameSize n = take n defaultGame

allDecks n = permutations $ take n defaultGame


bernoulli :: Double -> Dist Bool
bernoulli x = fromFreqs [(True, x), (False, (1 - x))]

deals :: Int -> Dist Deal
deals = Dist.uniform . allDecks

stateSpace :: Int -> Dist Game
stateSpace nPlayers = return Game `ap` 
                        deals nPlayers `ap` -- trueRoles
                        bernoulli 0.5   `ap`
                        makeVoteDucks `ap`
                        makeProposalIgnorance `ap`
                        makeProposalDucks `ap`
                        makeDecay

             --`ap` -- ladyWillLie
             --playerBeliefVar (1 / 3.0) nPlayers

data Game = Game { trueRoles :: Deal
                 , ladyWillLie :: Bool 
                 , willDuckOnRound :: [Bool]
                 , proposalIgnorant :: Double
                 , proposalDucks :: Double
                 , decay :: Double
                 }
  deriving (Show, Eq, Ord)



beliefVar :: Double -> Dist Double
beliefVar precision = Dist.uniform [0.0, precision..1.0]

playerBeliefVar :: Double -> Int -> Dist [Double]
playerBeliefVar precision n_players = constraint ?=<< var
  where var = Control.Monad.replicateM n_players $ beliefVar precision
        constraint in_var = 
          sum in_var == (sum $ Prelude.map (\x -> if roleSide x == Good then 1.0 else 0.0) $ gameSize n_players)

makeVoteDucks = mapM bernoulli [0.8, 0.6, 0.4]
makeProposalIgnorance =  certainly 0.8
makeProposalDucks = certainly 0.8
makeDecay = certainly 0.8

isGood :: Int -> Game -> Bool
isGood player game = roleSide (trueRoles game !! player) == Good
isEvil player game = roleSide (trueRoles game !! player) == Evil

playerNisRole :: Int -> String -> Dist.Event Game
playerNisRole n name game = roleName (trueRoles game !! n) == name

seePlayerN n role dist = playerNisRole n role ?=<< dist

playerNisSide :: Int -> Side -> Dist.Event Game
playerNisSide n side game =  getSide n game == side 

-- trustLevel n game = tableTrust game !! n

playerSeesPlayerAndClaims :: Int -> Int -> Side -> Dist.Event Game
playerSeesPlayerAndClaims p1 p2 claim game =
  if isGood p1 game
     then playerNisSide p2 claim game
     else if not (ladyWillLie game) then playerNisSide p2 claim game
          else playerNisSide p2 (otherSide claim) game

getSide x game = roleSide (trueRoles game !! x)

getRoundIgnorance round game = proposalIgnorant game * (decay game ** (round - 1)) > 0.5

getProposalDucks round game = proposalDucks game * (decay game ** (round - 1)) > 0.5


teamIsGood [] game = True
teamIsGood (x:xs) game = getSide x game == Good && (teamIsGood xs game)

doProposal team votes round game =
     foldl (||) False $ Prelude.map (proposalConstraints game) $ zip [0,1..] votes
     where 
     proposalConstraints game (player, vote) =
      if vote == 1 then
                   if getSide player game == Good then
                                             if teamIsGood team game then True
                                             else if getRoundIgnorance round game then True
                                             else False
                   else 
                      if not (teamIsGood team game) then True
                      else if getProposalDucks round game then True
                      else False
      else
        if getSide player game == Good then
            if not (teamIsGood team game) then True
            else if getRoundIgnorance round game then True
            else False
        else
            if teamIsGood team game then True
            else if getProposalDucks round game then True
            else False



-- doVote :: [Int] -> Int -> Dist.Event Game
doVote team successes round game = 
     foldl (||) False $ Prelude.map (makeConstraints game) $ [(successes, x) | x <- permutations team] 
     where 
     makeConstraints game (0, []) = True
     makeConstraints game (0, (x:xs)) = getSide x game == Evil && (makeConstraints game (0,xs))
     makeConstraints game (n, (x:xs)) = (getSide x game == Good || (ducks round game && (getSide x game == Evil))) && (makeConstraints game ((n - 1), xs))
     ducks round game = if round > 2 then False else ((willDuckOnRound game) !! round)





assertOnGame x game = x ?=<< game

assertions =  [(doVote [0, 2] 1 1), (playerSeesPlayerAndClaims 0 1 Evil)]

applyAssertions = foldl (\x y -> (assertOnGame y x)) 


dropNth i list = (take i list) ++ (drop (i+1) (list))
{-seePlayerN n role dist = do-}
    {-val <- dist-}
    {-Dist.filter (playerNisRole n role) val-}
    {-return val-}

--main = putStrLn $ show (seePlayerN 0 good1 deals)

playerReport n dist =
  "Player " ++ show n ++ ":\n" ++
    "  Is Good: " ++ show (playerNisSide n Good ?? dist) ++ "\n" ++
    "  Is Evil: " ++ show (playerNisSide n Evil ?? dist) ++ "\n"

ladyLoop nPlayers stateSpace assertions command ls = 
    let continueLoop = mainLoop nPlayers stateSpace assertions ls in
    let args = splitOn " " command in
    if length args < 4 then do
        putStrLn $ show args
        continueLoop
       else do
           putStrLn "Got it"
           let arg1 = read (args !! 1) :: Int
           let arg2 = read (args !! 2) :: Int
           let arg3 = if (read (args !! 3) :: Int) == 1 then Good else Evil
           mainLoop nPlayers stateSpace (assertions ++ [(playerSeesPlayerAndClaims arg1 arg2 arg3)]) (ls ++ [command])

assertLoop nPlayers stateSpace assertions command ls = 
    let continueLoop = mainLoop nPlayers stateSpace assertions ls in
    let args = splitOn " " command in
    if length args < 3 then do
        putStrLn $ show args
        continueLoop
       else do
           putStrLn "Got it"
           let arg1 = read (args !! 1) :: Int
           let arg2 = read (args !! 2) :: Int
           let side = if arg2 == 0 then Evil else Good in
            mainLoop nPlayers stateSpace (assertions ++ [(playerNisSide arg1 side)]) (ls ++ [command])

propLoop nPlayers stateSpace assertions command ls = 
    let continueLoop = mainLoop nPlayers stateSpace assertions ls in
    let args = splitOn " " command in
    if length args < 4 then do
        putStrLn $ show args
        continueLoop
       else do
           putStrLn "Got it"
           let arg1 = Prelude.map (\x -> (read x :: Int)) $ drop 1 $ splitOn "" (args !! 1)
           let arg2 = Prelude.map (\x -> (read x :: Int)) $ drop 1 $ splitOn "" (args !! 2)
           let arg3 = read (args !! 3) :: Double
           putStrLn $ show arg1
           putStrLn $ show arg2
           mainLoop nPlayers stateSpace (assertions ++ [(doProposal arg1 arg2 (arg3 - 1))]) (ls ++ [command])

voteLoop nPlayers stateSpace assertions command ls = 
    let continueLoop = mainLoop nPlayers stateSpace assertions ls in
    let args = splitOn " " command in
    if length args < 4 then do
        putStrLn $ show args
        continueLoop
       else do
           putStrLn "Got it"
           let arg1 = Prelude.map (\x -> (read x :: Int)) $ drop 1 $ splitOn "" (args !! 1)
           let arg2 = read (args !! 2) :: Int
           let arg3 = read (args !! 3) :: Int
           putStrLn $ show arg1
           putStrLn $ show arg2
           mainLoop nPlayers stateSpace (assertions ++ [(doVote arg1 arg2 (arg3 - 1))]) (ls ++ [command])

mainLoop nPlayers stateSpace assertions ls = do
    let continueLoop = mainLoop nPlayers stateSpace assertions ls
    putStrLn $ "Tim " ++ show nPlayers ++ "> "
    command <- getLine
    if command == "quit" 
       then return ()
    else if isPrefixOf "lol" command then 
      ladyLoop nPlayers stateSpace assertions command ls
    else if isPrefixOf "ass" command then 
      assertLoop nPlayers stateSpace assertions command ls
    else if isPrefixOf "ls" command then do
      putStrLn $ foldl (\x y -> x ++ (show $ fst y) ++ ": " ++ (snd y) ++ "\n") "" $ zip [0,1..] ls
      continueLoop
    else if isPrefixOf "deass" command then do
      let args = splitOn " " command 
      let arg1 = read (args !! 1) :: Int
      mainLoop nPlayers stateSpace (dropNth arg1 assertions) (dropNth arg1 ls)
    else if isPrefixOf "vot" command then 
      voteLoop nPlayers stateSpace assertions command ls
    else if isPrefixOf "pro" command then 
      propLoop nPlayers stateSpace assertions command ls
    else if command == "eval" then do
      trace <- Control.Monad.Parallel.replicateM 100 (Rnd.run $ Rnd.pick $ applyAssertions stateSpace assertions)
      let traceDist = Dist.uniform trace
      putStrLn $ foldl (++) "" $ Prelude.map (flip playerReport traceDist) [0..(nPlayers - 1)]
      continueLoop
    else do
      putStrLn "Unknown"
      continueLoop

main = do
    putStrLn "N players? "
    players <- getLine 
    let nplayers = read players :: Int
    mainLoop nplayers (stateSpace nplayers)  [] []

