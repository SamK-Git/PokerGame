from flask import Flask, request, jsonify
import random
from itertools import combinations
app = Flask(__name__)

@app.route("/debug", methods=["GET"])
def debug():
    return jsonify(game_state)

def dbg(msg):
    print(f"[DBG] {msg}")

SMALL_BLIND = 5
BIG_BLIND = 10
STARTING_STACK = 100
# Awaiting phases allow  display of last bet made before the game moves to the next phase
PHASES = ["waiting", "preflop", "awaiting_flop", "flop", "awaiting_turn", "turn", "awaiting_river", "river", "awaiting_showdown", "showdown"]

# -------------------------
# GAME STATE
# -------------------------
def new_game_state():
    players = {}
    # Always create 8 seats
    for i in range(1, 9):
        players[f"player{i}"] = {"name": "","stack": STARTING_STACK,"pot": 0,"bet": 0,"hand_contribution": 0,"cards": [],"folded": False,"all_in": False}
    return {
        "players": players,
        "community_cards": [],
        "pot": 0,
        "pots": [],
        "phase": "waiting",
        "dealer": "player1",
        "small_blind": None,
        "big_blind": None,
        "current_player": None,
        "deck": [],
        "hand_number": 0,
        "winners": [],
        "overall_winner": None,
        "num_players": 0,
        "last_action": "",
        "reveal_cards": False}

game_state = new_game_state()
# Determine the number of players logged in
def current_num_players():
    return len([p for p in game_state["players"].values() if p["name"] != ""])

# -------------------------
# DECK
# -------------------------
def new_deck():
    ranks = ["A","K","Q","J","10","9","8","7","6","5","4","3","2"]
    suits = ["♠","♥","♦","♣"]
    deck = [r + s for r in ranks for s in suits]
    random.shuffle(deck)
    return deck

# -------------------------
# TURN ORDER HELPERS
# -------------------------
def next_player(pid):
    # Extract seat number from "playerX"
    idx = int(pid.replace("player", ""))

    # Cycle through all 8 possible seats
    for _ in range(8):
        idx = (idx % 8) + 1
        npid = f"player{idx}"

        p = game_state["players"][npid]

        # Return only a seated, non-folded player
        # who still has chips
        if (p["name"] != "" and not p["folded"] and p["stack"] > 0):
            return npid

    return None

def ensure_current_player():
    cp = game_state.get("current_player")
    if cp is None or cp not in game_state["players"]:
        game_state["current_player"] = game_state["dealer"]

# -------------------------
# BETTING HELPERS
# -------------------------
def apply_bet(pid, amount, is_blind=False):
    p = game_state["players"][pid]
    amount = min(amount, p["stack"])
    p["stack"] -= amount
    p["bet"] += amount
    p["hand_contribution"] += amount
    game_state["pot"] += amount
    if not is_blind:
        p["acted"] = True
    # If the blind puts the player all-in, they are treated as having acted
    if is_blind and p["stack"] == 0:
        p["all_in"] = True
        p["acted"] = True
    elif p["stack"] == 0:
        p["all_in"] = True
     # Update main/side pot structure
    game_state["pots"] = compute_side_pots()

def max_bet():
    return max(p["bet"] for p in game_state["players"].values())

def reset_bets():
    for p in game_state["players"].values():
        p["bet"] = 0

# Determines the next player to act
def advance_turn():
    players = game_state["players"]
    current = game_state["current_player"]
    # Find next active player
    next_p = next_player(current)
    if next_p is None:
        #advance_phase()
        return
    while players[next_p]["folded"] or players[next_p]["all_in"]:
        next_p = next_player(next_p)
    game_state["current_player"] = next_p

# -------------------------
# NAME SETTING
# -------------------------
@app.route("/set_name", methods=["POST"])
def set_name():
    # Prevent joining during an active hand
    if game_state["phase"] not in ["waiting", "game_over"]:
        return jsonify({"error": "Cannot join during a game."})
    data = request.json
    pid = data["player_id"]
    name = data["name"]
    game_state["players"][pid]["name"] = name
    return jsonify({"status": "ok"})

# -------------------------
# DEAL NEW HAND
# -------------------------
def setup_hand():
    # Use frozen number of players for this hand
    n = game_state.get("num_players", 2)
    # Rotate dealer to the next player still in the game
    dealer = game_state.get("dealer")

    if dealer is None:
        dealer = active_players[0]
    else:
        next_dealer = next_player(dealer)

        if next_dealer is not None:
            dealer = next_dealer
        else:
            dealer = active_players[0]

    game_state["dealer"] = dealer
    game_state["hand_number"] += 1
    # Reset per-hand state
    for p in game_state["players"].values():
        p["cards"] = []
        p["bet"] = 0
        p["hand_contribution"] = 0
        p["folded"] = False
        p["all_in"] = False
    game_state["community_cards"] = []
    game_state["pot"] = 0
    game_state["pots"] = []
    game_state["phase"] = "preflop"
    game_state["winners"] = []
    game_state["reveal_cards"] = False
    game_state["last_action"] = ""
    # New deck
    game_state["deck"] = new_deck()
    # Deal hole cards
    for pid, p in game_state["players"].items():
        if p["name"] != "" and p["stack"] > 0:
            # Real seated player → deal cards
            p["cards"] = [game_state["deck"].pop(), game_state["deck"].pop()]
            p["folded"] = False
            p["acted"] = False
            p["bet"] = 0
        else:
            # Empty seat or eliminated player
            p["cards"] = []
            p["folded"] = True
            p["acted"] = True
            p["bet"] = 0
    # Assign blinds + first to act
    if n == 2:
        sb = dealer
        bb = next_player(dealer)
        first = dealer
    else:
        sb = next_player(dealer)
        bb = next_player(sb)
        first = next_player(bb)
    # Blind players
    game_state["small_blind_player"] = sb
    game_state["big_blind_player"] = bb
    # Blind amounts
    game_state["small_blind"] = SMALL_BLIND
    game_state["big_blind"] = BIG_BLIND
    # Post blinds
    apply_bet(sb, SMALL_BLIND, is_blind=True)
    apply_bet(bb, BIG_BLIND, is_blind=True)
    game_state["current_player"] = first
    ensure_current_player()

@app.route("/deal", methods=["POST"])
def deal():
    # Freeze number of players for the hand
    game_state["num_players"] = current_num_players()
    # Block dealing if the game is over
    if game_state["phase"] == "game_over":
        return jsonify({"status": "error", "message": "Game over"}), 400
    # Allow deal if game is brand new OR previous hand is over
    if game_state["hand_number"] > 0 and game_state["phase"] != "hand_over":
        return jsonify({"status": "error", "message": "Cannot deal: hand not over"}), 400
    setup_hand()
    return jsonify({"status": "ok"})

@app.route("/advance", methods=["POST"])
def advance():
    data = request.get_json(silent=True) or {}
    expected_phase = data.get("expected_phase")
    # Ignore a stale request from another browser. Example: browser asks to advance awaiting_flop, but another browser has already advanced it to flop.
    if expected_phase != game_state["phase"]:
        return jsonify({"status": "ignored","expected_phase": expected_phase,"actual_phase": game_state["phase"]})
    advance_phase()
    return jsonify({"status": "ok","phase": game_state["phase"]})

# Used to set up a game at a specific point
@app.route("/force_phase", methods=["POST"])
def force_phase():
    data = request.json

    phase = data["phase"]
    community = data["community"]

    p1_cards = data["p1_cards"]
    p2_cards = data["p2_cards"]
    p3_cards = data["p3_cards"]

    p1_stack = data["p1_stack"]
    p2_stack = data["p2_stack"]
    p3_stack = data["p3_stack"]

    pot = data["pot"]
    dealer = data["dealer"]
    current_player = data["current_player"]

    # --- Set phase ---
    game_state["phase"] = phase

    # --- Set community cards ---
    game_state["community_cards"] = community

    # --- Set hole cards ---
    game_state["players"]["player1"]["cards"] = p1_cards
    game_state["players"]["player2"]["cards"] = p2_cards
    game_state["players"]["player3"]["cards"] = p3_cards

    # --- Set stacks ---
    game_state["players"]["player1"]["stack"] = p1_stack
    game_state["players"]["player2"]["stack"] = p2_stack
    game_state["players"]["player3"]["stack"] = p3_stack

    # --- Set names ---
    game_state["players"]["player1"]["name"] = data["p1_name"]
    game_state["players"]["player2"]["name"] = data["p2_name"]
    game_state["players"]["player3"]["name"] = data["p3_name"]

    # --- Set blinds ---
    game_state["small_blind"] = data["small_blind"]
    game_state["big_blind"] = data["big_blind"]

    # --- Reset bets and contributions ---
    for pid in ["player1", "player2", "player3"]:
        game_state["players"][pid]["bet"] = 0
        game_state["players"][pid]["hand_contribution"] = 0
        game_state["players"][pid]["folded"] = False
        game_state["players"][pid]["all_in"] = False
        game_state["players"][pid]["acted"] = False

    # --- Remove unused seats from this test ---
    for pid, p in game_state["players"].items():
        if pid not in ["player1", "player2", "player3"]:
            p["folded"] = True
            p["acted"] = True
            p["all_in"] = False
            p["stack"] = 0
            p["cards"] = []
            p["hand_contribution"] = 0
            p["bet"] = 0

    # --- Set pot ---
    game_state["pot"] = pot
    game_state["pots"] = []

    # --- Set dealer and player count ---
    game_state["dealer"] = dealer
    game_state["num_players"] = 3

    # --- Set current player ---
    game_state["current_player"] = current_player

    # --- Build deck and remove used cards ---
    used = set(
        community
        + p1_cards
        + p2_cards
        + p3_cards)

    deck = new_deck()
    game_state["deck"] = [
        c for c in deck
        if c not in used]

    return jsonify({
        "status": "ok",
        "message": "3-player phase forced successfully"})

# -------------------------
# PHASE ADVANCEMENT
# -------------------------
def advance_phase():
    phase = game_state["phase"]
    # Determine whether anyone can still act
    active_players = [pid for pid, p in game_state["players"].items() if p["name"] != "" and not p["folded"]]
    players_who_can_act = [pid for pid in active_players if not game_state["players"][pid]["all_in"] and game_state["players"][pid]["stack"] > 0]
    no_more_betting = len(players_who_can_act) <= 1
    # -----------------------------------------
    # DEAL FLOP
    # -----------------------------------------
    if phase == "awaiting_flop":
        game_state["deck"].pop()  # burn card
        flop = [
            game_state["deck"].pop(),
            game_state["deck"].pop(),
            game_state["deck"].pop()
        ]
        game_state["community_cards"] = flop
        game_state["last_action"] = ""
        if not no_more_betting:
            n = game_state.get("num_players", 2)
            if n == 2:
                first = game_state["big_blind_player"]
            else:
                first = next_player(game_state["dealer"]) or game_state["dealer"]
            game_state["current_player"] = first
        if no_more_betting:
            game_state["phase"] = "awaiting_turn"
        else:
            game_state["phase"] = "flop"
        return
    # -----------------------------------------
    # DEAL TURN
    # -----------------------------------------
    elif phase == "awaiting_turn":
        game_state["deck"].pop()  # burn card
        turn = game_state["deck"].pop()
        game_state["community_cards"].append(turn)
        game_state["last_action"] = ""
        # Set first player to act only AFTER the turn has been dealt
        if not no_more_betting:
            n = game_state.get("num_players", 2)

            if n == 2:
                first = game_state["big_blind_player"]
            else:
                first = next_player(game_state["dealer"]) or game_state["dealer"]

            game_state["current_player"] = first

        if no_more_betting:
            game_state["phase"] = "awaiting_river"
        else:
            game_state["phase"] = "turn"
    # -----------------------------------------
    # DEAL RIVER
    # -----------------------------------------
    elif phase == "awaiting_river":
        game_state["deck"].pop()  # burn card
        river = game_state["deck"].pop()
        game_state["community_cards"].append(river)
        game_state["last_action"] = ""
        # Set first player to act only AFTER the river has been dealt
        if not no_more_betting:
            n = game_state.get("num_players", 2)

            if n == 2:
                first = game_state["big_blind_player"]
            else:
                first = next_player(game_state["dealer"]) or game_state["dealer"]

            game_state["current_player"] = first

        if no_more_betting:
            game_state["phase"] = "awaiting_showdown"
        else:
            game_state["phase"] = "river"

        return
    # -----------------------------------------
    # SHOWDOWN
    # -----------------------------------------
    elif phase == "awaiting_showdown":
        evaluate_showdown()
        return

def maybe_advance_after_action(pid):
    players = game_state["players"]
    active_players = [p for p in players if players[p]["name"] != "" and not players[p]["folded"]]
    # Only one active player remains
    if len(active_players) == 1:
        winner = active_players[0]
        game_state["winners"] = [winner]
        game_state["phase"] = "hand_over"
        return
    # Determine who has acted
    # Determine who is all-in
    all_in_players = [p for p in active_players if players[p]["all_in"]]
    # Only players who are still able to act need to have acted
    players_who_can_act = [p for p in active_players if not players[p]["all_in"]]
    all_acted = all(players[p].get("acted", False) for p in players_who_can_act)
    # -------------------------------------------------
    # ALL-IN / END OF BETTING ROUND
    # -------------------------------------------------
    # If all active players have acted and all-but-one are all-in, pause before dealing the next cards.
    if len(all_in_players) >= len(active_players) - 1 and all_acted:
        game_state["reveal_cards"] = True
        if game_state["phase"] == "preflop": game_state["phase"] = "awaiting_flop"
        elif game_state["phase"] == "flop": game_state["phase"] = "awaiting_turn"
        elif game_state["phase"] == "turn": game_state["phase"] = "awaiting_river"
        elif game_state["phase"] == "river": game_state["phase"] = "awaiting_showdown"
        for p in game_state["players"].values(): p["acted"] = False
        return
    # -------------------------------------------------
    # NORMAL BETTING ROUND
    # -------------------------------------------------
    # Only players who can still bet need to have matching bets.
    # An all-in player may legitimately have a smaller bet.
    players_who_can_bet = [p for p in active_players if not players[p]["all_in"]]
    bets = [players[p]["bet"] for p in players_who_can_bet]
    all_bets_equal = (len(players_who_can_bet) <= 1 or len(set(bets)) == 1)
    if all_bets_equal and all_acted:
        # River betting finished
        if game_state["phase"] == "river":
            game_state["phase"] = "awaiting_showdown"
            for p in game_state["players"].values():
                p["acted"] = False
            return
        # Move to transition phase for next street
        if game_state["phase"] == "preflop":
            game_state["phase"] = "awaiting_flop"
        elif game_state["phase"] == "flop":
            game_state["phase"] = "awaiting_turn"
        elif game_state["phase"] == "turn":
            game_state["phase"] = "awaiting_river"
        reset_bets()
        # Reset acted flags for the new betting round
        for p in game_state["players"].values():
            if p["name"] != "" and not p["folded"]:
                p["acted"] = False
        return
    # Betting round not finished
    advance_turn()

# -------------------------
# ACTION ENDPOINTS
# -------------------------
def require_turn(pid):
    return pid == game_state["current_player"]

@app.route("/fold", methods=["POST"])
def fold():
    pid = request.json["player_id"]
    player = game_state["players"][pid]
    game_state["players"][pid]["acted"] = True
    # Do NOT add bet to pot again; it's already there from apply_bet
    player["bet"] = 0
    player["folded"] = True
    game_state["pots"] = compute_side_pots()
    game_state["last_action"] = (f'{game_state["players"][pid]["name"]} folds')
    # Check if only one player remains in the hand
    players = game_state["players"]
    contesting_players = [pid for pid, p in players.items() if p["name"] != "" and not p["folded"] and (p["stack"] > 0 or p["bet"] > 0)]
    if len(contesting_players) == 1:
        winner = contesting_players[0]
        game_state["players"][winner]["stack"] += game_state["pot"]
        game_state["pot"] = 0
        game_state["phase"] = "hand_over"
        game_state["winners"] = [winner]
        for pid, p in players.items(): p["bet"] = 0
        return jsonify({"status": "ok", "winner": winner})
    maybe_advance_after_action(pid)
    return jsonify({"status": "ok"})

@app.route("/check", methods=["POST"])
def check():
    pid = request.json["player_id"]
    if not require_turn(pid):
        return jsonify({"status": "error", "message": "Not your turn"}), 400
    if game_state["players"][pid]["bet"] != max_bet():
        return jsonify({"status": "error", "message": "Cannot check"}), 400
    # Mark that this player has acted in this betting round
    game_state["players"][pid]["acted"] = True
    game_state["last_action"] = (f'{game_state["players"][pid]["name"]} checks')
    maybe_advance_after_action(pid)
    return jsonify({"status": "ok"})

@app.route("/call", methods=["POST"])
def call():
    pid = request.json["player_id"]
    if pid != game_state["current_player"]:
        return jsonify({"status": "error", "message": "Not your turn"}), 400
    to_call = max_bet() - game_state["players"][pid]["bet"]
    if to_call > 0:
        apply_bet(pid, to_call)
    game_state["players"][pid]["acted"] = True
    # Last action message
    #player_name = player.get("name", pid)
    #game_state["last_action"] = (f'{game_state["players"][pid]["name"]} calls {to_call}')
    game_state["last_action"] = (f'{game_state["players"][pid]["name"]} calls {to_call}')
    maybe_advance_after_action(pid)

    print("--- AFTER maybe_advance_after_action ---")
    print("current_player:", game_state["current_player"])
    print("phase:", game_state["phase"])
    return jsonify({"status": "ok"})

@app.route("/bet", methods=["POST"])
def bet():
    pid = request.json["player_id"]
    if not require_turn(pid):
        return jsonify({"status": "error", "message": "Not your turn"}), 400
    if max_bet() > 0:
        return jsonify({"status": "error", "message": "Cannot bet, must call or raise"}), 400
    amount = int(request.json["amount"])
    apply_bet(pid, amount)
    #SK added this - Everyone else must act again after this bet
    for other_pid, p in game_state["players"].items():
        if not p["all_in"] and not p["folded"] and other_pid != pid:
            p["acted"] = False
    game_state["players"][pid]["acted"] = True
     # Last action message
    game_state["last_action"] = (f'{game_state["players"][pid]["name"]} bets {amount}')
    maybe_advance_after_action(pid)
    return jsonify({"status": "ok"})

@app.route("/raise", methods=["POST"])
def raiseto_bet():
    pid = request.json["player_id"]
    if not require_turn(pid):
        return jsonify({"status": "error", "message": "Not your turn"}), 400
    amount = int(request.json["amount"])
    # NOT SURE IF BELOW IS REQUIRED (other conditions prevent amount < BIG_BLIND) BUT RETAIN
    if amount < BIG_BLIND:
        return jsonify({"status": "error", "message": "Raise too small"}), 400
    apply_bet(pid, amount)
    # Everyone else must act again after this raise
    for other_pid, p in game_state["players"].items():
        if p["name"] != "" and not p["folded"] and other_pid != pid:
            p["acted"] = False
    game_state["players"][pid]["acted"] = True
    # Last action message
    game_state["last_action"] = (f'{game_state["players"][pid]["name"]} raises {amount}')
    maybe_advance_after_action(pid)
    return jsonify({"status": "ok"})

# -------------------------
# RESET = NEW GAME + NEW HAND
# -------------------------
@app.route("/reset", methods=["POST"])
def reset():
    global game_state
    old_players = game_state["players"]
    game_state = new_game_state()
    # Check if ANY old player had a name
    any_named = any(p["name"] != "" for p in old_players.values())
    # Restore all currently registered players
    if any_named:
        # Normal case: restore names
        for pid, pdata in old_players.items():
            game_state["players"][pid]["name"] = pdata["name"]
    game_state["game_winner"] = None
    return jsonify({"status": "ok"})

@app.post("/join")
def join():
    data = request.get_json()
    name = data.get("name")
    # Prevent joining during an active hand
    if game_state["phase"] not in ["waiting", "game_over"]:
        return {"error": "Cannot join during a game. Please wait for the next game."}
    # Prevent duplicate names
    if name in [p["name"] for p in game_state["players"].values()]:
        return {"error": "Name already taken"}
    # ⭐ If Sam logs in, ALWAYS give player1
    if name == "Sam":
        game_state["players"]["player1"]["name"] = "Sam"
        return {"success": True, "seat": "player1"}
    # ⭐ Everyone else fills seats 2–8
    for i in range(2, 9):
        pid = f"player{i}"
        if game_state["players"][pid]["name"] == "":
            game_state["players"][pid]["name"] = name
            return {"success": True, "seat": pid}
    return {"error": "No seats available"}

# -------------------------
# HAND EVALUATION
# -------------------------
RANK_ORDER = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 11, "Q": 12, "K": 13, "A": 14}

def card_rank(card):
    return RANK_ORDER[card[:-1]]

def card_suit(card):
    return card[-1]

def hand_rank_5(cards):
    ranks = sorted([card_rank(c) for c in cards], reverse=True)
    suits = [card_suit(c) for c in cards]
    is_flush = len(set(suits)) == 1
    is_straight = False
    rset = sorted(set(ranks), reverse=True)
    if len(rset) == 5 and rset[0] - rset[4] == 4:
        is_straight = True
    if set(ranks) == {14, 5, 4, 3, 2}:
        is_straight = True
        ranks = [5, 4, 3, 2, 1]
    counts = {r: ranks.count(r) for r in ranks}
    count_values = sorted(counts.values(), reverse=True)
    sorted_by_count = sorted(counts.items(), key=lambda x: (-x[1], -x[0]))
    if is_straight and is_flush:
        return (8, max(ranks))
    if 4 in count_values:
        four = sorted_by_count[0][0]
        kicker = max(r for r in ranks if r != four)
        return (7, four, kicker)
    if 3 in count_values and 2 in count_values:
        three = sorted_by_count[0][0]
        pair = sorted_by_count[1][0]
        return (6, three, pair)
    if is_flush:
        return (5, ranks)
    if is_straight:
        return (4, max(ranks))
    if 3 in count_values:
        three = sorted_by_count[0][0]
        kickers = sorted([r for r in ranks if r != three], reverse=True)
        return (3, three, kickers)
    if count_values.count(2) >= 2:
        pairs = sorted([r for r, c in counts.items() if c == 2], reverse=True)
        kicker = max(r for r in ranks if r not in pairs)
        return (2, pairs, kicker)
    if 2 in count_values:
        pair = sorted_by_count[0][0]
        kickers = sorted([r for r in ranks if r != pair], reverse=True)
        return (1, pair, kickers)
    return (0, ranks)

def best_5_of_7(cards7):
    best = None
    for combo in combinations(cards7, 5):
        hr = hand_rank_5(list(combo))
        if best is None or hr > best:
            best = hr
    return best

def hand_description(hand_rank):
    if hand_rank is None:
        return ""
    category = hand_rank[0]
    rank_names = {
        14: "Ace",
        13: "King",
        12: "Queen",
        11: "Jack",
        10: "Ten",
        9: "Nine",
        8: "Eight",
        7: "Seven",
        6: "Six",
        5: "Five",
        4: "Four",
        3: "Three",
        2: "Two",
        1: "Ace",}
    plural_rank_names = {
        14: "Aces",
        13: "Kings",
        12: "Queens",
        11: "Jacks",
        10: "Tens",
        9: "Nines",
        8: "Eights",
        7: "Sevens",
        6: "Sixes",
        5: "Fives",
        4: "Fours",
        3: "Threes",
        2: "Twos",}
    # High Card
    if category == 0:
        high = hand_rank[1][0]
        return f"{rank_names[high]} high"
    # One Pair
    if category == 1:
        pair = hand_rank[1]
        return f"a Pair of {plural_rank_names[pair]}"
    # Two Pair
    if category == 2:
        high_pair = hand_rank[1][0]
        low_pair = hand_rank[1][1]
        return (f"Two Pair, "f"{plural_rank_names[high_pair]} and "f"{plural_rank_names[low_pair]}")
    # Three of a Kind
    if category == 3:
        three = hand_rank[1]
        return f"Three {plural_rank_names[three]}"
    # Straight
    if category == 4:
        high = hand_rank[1]
        return f"a {rank_names[high]}-high Straight"
    # Flush
    if category == 5:
        high = hand_rank[1][0]
        return f"a {rank_names[high]}-high Flush"
    # Full House
    if category == 6:
        three = hand_rank[1]
        pair = hand_rank[2]
        return (f"a Full House, "f"{plural_rank_names[three]} over "f"{plural_rank_names[pair]}")
    # Four of a Kind
    if category == 7:
        four = hand_rank[1]
        return f"Four {plural_rank_names[four]}"
    # Straight Flush
    if category == 8:
        high = hand_rank[1]
        if high == 14:
            return "a Royal Flush"
        return f"a {rank_names[high]}-high Straight Flush"
    return "an Unknown Hand"

def compute_side_pots():
    players = game_state["players"]
    # All players who have contributed chips to this hand.
    # Folded players MUST be included when calculating
    # pot amounts because their chips remain in the pot.
    contributions = {pid: p.get("hand_contribution", 0) for pid, p in players.items() if p["name"] != "" and p.get("hand_contribution", 0) > 0}
    if not contributions:
        return []
    # Each different contribution level creates
    # a possible pot boundary.
    levels = sorted(set(contributions.values()))
    pots = []
    previous_level = 0
    for level in levels:
        layer = level - previous_level
        # Anyone who contributed at least this much
        # has chips in this layer.
        contributors = [pid for pid, amount in contributions.items() if amount >= level]
        amount = layer * len(contributors)
        if amount > 0:
            # Folded players contribute money but
            # cannot win the pot.
            eligible = [pid for pid in contributors if not players[pid].get("folded", False)]
            pots.append({"amount": amount, "eligible": eligible})
        previous_level = level
    # Give the pots display names
    for i, pot in enumerate(pots):
        if i == 0:
            pot["name"] = "Main Pot"
        else:
            pot["name"] = f"Side Pot {i}"
    return pots

def evaluate_showdown():
    players = game_state["players"]
    community = game_state["community_cards"]
    # Build the final pot structure
    pots = compute_side_pots()
    game_state["pots"] = pots
    # Keep track of everyone who wins at least one pot
    all_winners = []
    for pot in pots:
        eligible = [pid for pid in pot["eligible"] if players[pid]["name"] != "" and not players[pid]["folded"]]
        if not eligible:
            continue
        best_rank = None
        pot_winners = []
        # -----------------------------------------
        # Determine winner(s) of THIS pot
        # -----------------------------------------
        for pid in eligible:
            cards = (players[pid]["cards"]+ community)
            hr = best_5_of_7(cards)
            if (best_rank is None or hr > best_rank):
                best_rank = hr
                pot_winners = [pid]
            elif hr == best_rank:
                pot_winners.append(pid)
        # -----------------------------------------
        # Pay THIS pot
        # -----------------------------------------
        if pot_winners:
            amount = pot["amount"]
            share = amount // len(pot_winners)
            remainder = amount % len(pot_winners)
            for pid in pot_winners:
                players[pid]["stack"] += share
                if pid not in all_winners:
                    all_winners.append(pid)
            # For now, give any odd chip to the
            # first winner.
            if remainder:
                players[pot_winners[0]]["stack"] += remainder
            # Store result for frontend/debugging
            pot["winners"] = pot_winners
            pot["winning_hand"] = hand_description(best_rank)
    # -----------------------------------------
    # HAND RESULT
    # -----------------------------------------
    game_state["winners"] = all_winners
    # All pot money has now been distributed
    game_state["pot"] = 0
    # Reset current street bets
    for p in players.values():
        p["bet"] = 0
    # -----------------------------------------
    # GAME OVER CHECK
    # -----------------------------------------
    alive = [pid for pid, p in players.items() if p["name"] != "" and p["stack"] > 0]
    if len(alive) == 1:
        # Overall game winner
        game_state["overall_winner"] = alive[0]
    else:
        game_state["overall_winner"] = None
    # Keep the normal end-of-hand phase
    game_state["phase"] = "hand_over"

# -------------------------
# STATE
# -------------------------
@app.route("/state", methods=["GET"])
def state():
    ensure_current_player()
    return jsonify(game_state)

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
     app.run(host="0.0.0.0", port=5000, debug=True)




