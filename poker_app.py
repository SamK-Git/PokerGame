import math
import streamlit as st
import streamlit.components.v1 as components
import requests
from streamlit_autorefresh import st_autorefresh
import time

# -------------------------
# PAGE CONFIGURATION
# -------------------------
st.set_page_config(layout="wide")

# -------------------------
# CUSTOM CSS
# -------------------------
st.markdown(
    """
    <style>
    /* Reduce top padding of the whole Streamlit page */
    .block-container {padding-top: 2rem !important;padding-bottom: 0 !important;}
    /* First line styling */
    .first-line {font-size: 28px !important;font-weight: 700 !important;margin: 0 !important;padding: 0 !important;line-height: 1.2 !important;white-space: nowrap;}.game-info {margin: 0 !important;padding: 0 !important;}
    /* Add a little extra gap only on Sam's screen */
    .host-game-info {margin-top: 16px !important;}
   /* Reduce spacing between Streamlit blocks */
    div[data-testid="stVerticalBlock"] {margin-top: -10px !important;}
    /* Remove extra bottom margin from last block */
    div[data-testid="stVerticalBlock"]:last-child {margin-bottom: 0 !important;padding-bottom: 0 !important;}
    /* Remove global bottom padding */
    main {padding-bottom: 0 !important;}
    /* Keep horizontal blocks tight */
    div[data-testid="stHorizontalBlock"] {align-items: center !important;margin-bottom: 0 !important;}
    /* Remove extra margin around buttons */
    div[data-testid="stButton"] {margin: 0 !important;}
    /* Compact status message */
    .st-key-status_area div[data-testid="stAlert"] {margin-top: 20px !important;}
    </style>""",unsafe_allow_html=True,)

# -------------------------
# CONFIGURATION
# -------------------------
HOST_PASSWORD = "sam123"
API_BASE = "https://sams-poker-api.onrender.com"
FOLD_URL = f"{API_BASE}/fold"
CHECK_URL = f"{API_BASE}/check"
CALL_URL = f"{API_BASE}/call"
BET_URL = f"{API_BASE}/bet"
RAISE_URL = f"{API_BASE}/raise"
DEAL_URL = f"{API_BASE}/deal"
RESET_URL = f"{API_BASE}/reset"
ADV_URL = f"{API_BASE}/advance"
STATE_URL = f"{API_BASE}/state"
BIG_BLIND = 10

# -------------------------
# TABLE DIMENSIONS
# -------------------------
TABLE_WIDTH = 900
TABLE_HEIGHT = 450
SEAT_BOX_W = 125
SEAT_BOX_H = 60

# -------------------------
# SEAT POSITIONS
# -------------------------
def get_seat_positions(num_players):
    cx = TABLE_WIDTH / 2
    cy = TABLE_HEIGHT / 2
    rx = TABLE_WIDTH / 2 - SEAT_BOX_W / 2 + 10
    ry = TABLE_HEIGHT / 2 - SEAT_BOX_H / 2 + 10
    positions = []
    if num_players <= 0:
        return positions
    # Start at top and move clockwise
    start_angle = -90
    for i in range(num_players):
        angle_deg = (start_angle + (360 / num_players) * i)
        angle_rad = math.radians(angle_deg)
        x = (cx + rx * math.cos(angle_rad) - SEAT_BOX_W / 2)
        y = (cy + ry * math.sin(angle_rad) - SEAT_BOX_H / 2)
        # Force top and bottom seats onto
        # exactly the same vertical centre line
        if abs(math.cos(angle_rad)) < 0.01:
            x = cx - SEAT_BOX_W / 2
        positions.append((round(x), round(y)))
    return positions

# -------------------------
# BACKEND HELPERS
# -------------------------
import base64

def play_sound(filename=None):
    if filename:
        with open(filename, "rb") as f:
            sound = base64.b64encode(f.read()).decode()

        audio_html = f"""<audio autoplay><source src="data:audio/mp3;base64,{sound}" type="audio/mp3"></audio>"""

    else:
        audio_html = ""

    components.html(audio_html,height=0,width=0,)

def fetch_game_state():
    try:
        resp = requests.get(STATE_URL,timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        st.error("Cannot reach game server. ""Is it running?")
        st.stop()

def post(url, payload=None):
    try:
        resp = requests.post(url,json=payload or {},timeout=5)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        return resp.status_code, data
    except Exception as error:
        return 0, {"error": str(error)}

# -------------------------
# FORCE PHASE TEST
# -------------------------
def force_phase(phase):
    payload = {
        "phase": phase,
        "community": [],

        "p1_cards": ["Q♠", "Q♦"],
        "p2_cards": ["J♣", "J♥"],
        "p3_cards": ["10♣", "10♥"],

        "p1_stack": 50,
        "p2_stack": 100,
        "p3_stack": 150,

        "pot": 0,

        "dealer": "player1",
        "current_player": "player1",

        "big_blind": 10,
        "small_blind": 5,

        "p1_name": "sam",
        "p2_name": "chris",
        "p3_name": "player 3",}

    requests.post(f"{API_BASE}/force_phase",json=payload)

# -------------------------
# POKER TABLE HTML
# -------------------------
def card_html(card, size="hole"):
    if not card:
        return ""
    suit = card[-1]
    rank = card[:-1]
    # Red suits / black suits
    colour = ("#d71920" if suit in ["♥", "♦"] else "#111111")
    # Slightly larger community cards
    if size == "community":
        width = 52
        height = 72
        rank_size = 17
        suit_size = 29
    else:
        width = 42
        height = 58
        rank_size = 14
        suit_size = 23
    return f"""
    <div style="
        display:inline-block;
        position:relative;
        width:{width}px;
        height:{height}px;
        background:white;
        border:1px solid #bbbbbb;
        border-radius:6px;
        margin:2px;
        color:{colour};
        box-shadow:0 2px 4px rgba(0,0,0,0.25);
        vertical-align:middle;
        font-family:Arial, sans-serif;
    ">
        <div style="
            position:absolute;
            top:3px;
            left:5px;
            font-size:{rank_size}px;
            font-weight:700;
            line-height:1;
        ">
            {rank}
        </div>
        <div style="
            position:absolute;
            top:50%;
            left:50%;
            transform:translate(-50%, -50%);
            font-size:{suit_size}px;
            line-height:1;
        ">
            {suit}
        </div>
        <div style="
            position:absolute;
            bottom:3px;
            right:5px;
            font-size:{rank_size}px;
            font-weight:700;
            line-height:1;
            transform:rotate(180deg);
        ">
            {rank}
        </div>
    </div>
    """

def build_table_html(game_state):
    my_player_id = st.session_state["player_id"]
    players_all = game_state.get("players",{})
    # Only draw players who have names
    players = {pid: p for pid, p in players_all.items() if p["name"] != ""}
    num_players = len(players)
    seat_positions = get_seat_positions(num_players)
    # -------------------------------------------------
    # REVEAL CARDS
    # -------------------------------------------------
    # The backend sets reveal_cards = True only when all betting decisions are complete and no further betting is possible
    reveal_cards = game_state.get("reveal_cards",False)
    html = f"""
    <div style="
        position: relative;
        width: {TABLE_WIDTH}px;
        height: {TABLE_HEIGHT}px;
        margin: 0 auto;
        margin-top: 10px;
        background-color: darkgreen;
        border-radius: 250px;
    ">
    """
    # -------------------------------------------------
    # POT AND COMMUNITY CARDS
    # -------------------------------------------------
    html += f"""
    <div style="
        position:absolute;
        top:{TABLE_HEIGHT / 2 - 60}px;
        left:{TABLE_WIDTH / 2 - 90}px;
        color:white;
        text-align:center;
    ">
    """
    pots = game_state.get("pots", [])
    if pots:
        pot_parts = []
        for pot in pots:
            pot_parts.append(f"{pot.get('name', 'Pot')}: "f"{pot.get('amount', 0)}")
        html += (" | ".join(pot_parts)+ "<br>")
    else:
        html += (f"Pot: "f"{game_state.get('pot', 0)}"f"<br>")
    community_html = "".join(
        card_html(c, "community")
        for c in game_state.get("community_cards",[]))
    html += f"""
    <div style="
        margin-top:5px;
        white-space:nowrap;
    ">
        {community_html}
    </div>
    """
    html += "</div>"
    # -------------------------------------------------
    # PLAYERS
    # -------------------------------------------------
    for i, (pid, pdata) in enumerate(players.items()):
        # ---------------------------------------------
        # HOLE CARDS
        # ---------------------------------------------
        # Normally a player sees only their own cards.  Once the backend sets reveal_cards = True, all NON-FOLDED players' cards are visible to everyone. Folded players' cards remain hidden.
        # ---------------------------------------------
        if (pid == my_player_id or (reveal_cards and not pdata.get("folded", False))):
            cards = pdata.get("cards",[])
            cards_html = "".join(card_html(c, "hole") for c in cards)
        else:
            cards_html = ""
        # ---------------------------------------------
        # PLAYER POSITION
        # ---------------------------------------------
        x, y = seat_positions[i]
        angle_deg = (-90 + (360 / num_players) * i)
        # Force exact top and bottom seats onto the same horizontal centre line
        if (abs(angle_deg + 90) < 0.01 or abs(angle_deg - 90) < 0.01):
            x = (TABLE_WIDTH - SEAT_BOX_W) / 2
        name = pdata.get("name") or pid
        stack = pdata.get("stack", 0)
        bet = pdata.get("bet", 0)
        # ---------------------------------------------
        # PLAYER BOX STYLE
        # ---------------------------------------------
        is_active = (pid == game_state.get("current_player"))
        is_folded = pdata.get("folded",False)
        is_eliminated = (pdata.get("stack", 0) == 0 and not pdata.get("all_in", False))
        if is_folded or is_eliminated:
            box_style = ("background-color: white; ""color: black; ""border: 1px solid black; ""opacity: 0.5;")
        elif is_active:
            box_style = ("background-color: yellow; ""color: black; ""border: 2px solid black;")
        else:
            box_style = ("background-color: white; ""color: black; ""border: 1px solid black;")
        # ---------------------------------------------
        # WORK OUT BOTTOM SEATS
        # ---------------------------------------------
        is_bottom = (45<= angle_deg <= 135)
        lift = (-50 if is_bottom else 0)
        # ---------------------------------------------
        # PLAYER BOX
        # ---------------------------------------------
        html += f"""
        <div style="
            position:absolute;
            left:{x}px;
            top:{y + lift}px;
            width:{SEAT_BOX_W}px;
            box-sizing:border-box;
            text-align:center;
            padding:6px 10px;
            border-radius:8px;
            font-size:14px;
            {box_style}
        ">
            <div style="font-weight:bold;">
                {name}
            </div>
            <div>
                Stack: {stack}
            </div>
            <div>
                Bet: {bet}
            </div>
            <div>
                {cards_html}
            </div>
        </div>
        """
        # ---------------------------------------------
        # DEALER BUTTON
        # ---------------------------------------------
        if pid == game_state.get("dealer"):
            if is_bottom:
                # Bottom seats: move dealer button up and right
                dealer_left = x + 95
                dealer_top = y + lift - 15
            else:
                # Other seats: keep existing position
                dealer_left = x + 95
                dealer_top = y - 10
            html += f"""
            <div style="
                position:absolute;
                left:{dealer_left}px;
                top:{dealer_top}px;
                width:24px;
                height:24px;
                background-color:white;
                color:black;
                border-radius:50%;
                border:2px solid black;
                text-align:center;
                font-weight:bold;
                line-height:24px;
                font-size:14px;
            ">
                D
            </div>
            """
        # ---------------------------------------------
        # SMALL BLIND / BIG BLIND BUTTONS
        # ---------------------------------------------
        blind_label = None

        if pid == game_state.get("small_blind_player"):
            blind_label = "SB"
        elif pid == game_state.get("big_blind_player"):
            blind_label = "BB"

        if blind_label:
            if is_bottom:
                blind_left = x + 95
                blind_top = y + lift + 15
            else:
                blind_left = x + 95
                blind_top = y + 20

            html += f"""
            <div style="
                position:absolute;
                left:{blind_left}px;
                top:{blind_top}px;
                width:28px;
                height:24px;
                background-color:white;
                color:black;
                border-radius:12px;
                border:2px solid black;
                text-align:center;
                font-weight:bold;
                line-height:24px;
                font-size:11px;
            ">
                {blind_label}
            </div>
            """

    html += "</div>"
    return html

# -------------------------
# LOGIN SCREEN
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.write("")
    st.title("Welcome to the Poker Table")
    st.write("""This is a multiplayer poker game. Enter your name and the game password. Player 1 is the host.""")
    name = st.text_input("Your name")
    password = st.text_input("Game password",type="password")
    if st.button("Continue"):
        if not name:
            st.warning("Please enter a name.")
        else:
            # -------------------------
            # HOST
            # -------------------------
            if password == HOST_PASSWORD:
                st.session_state.player_id = ("player1")
                post(f"{API_BASE}/set_name",{"player_id": "player1","name": name})
            # -------------------------
            # NON-HOST
            # -------------------------
            else:
                status, response = post(f"{API_BASE}/join",{"name": name})
                if "error" in response:
                    st.error(response["error"])
                    st.stop()
                st.session_state.player_id = (response["seat"])
            st.session_state.player_name = (name)
            st.session_state.logged_in = True
            st.rerun()
    st.stop()

# -------------------------
# AUTO REFRESH
# -------------------------
st_autorefresh(interval=4000,key="poker_refresh")

# -------------------------
# SESSION STATE
# -------------------------
if "deal_next_hand" not in st.session_state:
    st.session_state.deal_next_hand = False

if "last_sound_hand" not in st.session_state:
    st.session_state.last_sound_hand = 0

if "flop_sound_hand" not in st.session_state:
    st.session_state.flop_sound_hand = 0

if "turn_sound_hand" not in st.session_state:
    st.session_state.turn_sound_hand = 0

if "river_sound_hand" not in st.session_state:
    st.session_state.river_sound_hand = 0

# -------------------------
# CURRENT PLAYER + GAME STATE
# -------------------------
player_id = st.session_state.player_id
player_name = st.session_state.player_name
is_host = (player_id == "player1")
# Get current state from backend FIRST
game_state = fetch_game_state()

# -------------------------------------------------
# BACKEND RESTART DETECTION
# -------------------------------------------------
backend_player = game_state.get("players",{}).get(player_id,{})
if backend_player.get("name", "") == "":
    st.session_state.logged_in = False
    st.session_state.deal_next_hand = False
    st.rerun()
# Only continue after backend/player has been verified
phase = game_state.get("phase")

# -------------------------
# SOUND CONTROL
# -------------------------
hand_number = game_state.get("hand_number", 0)

# Reset sound markers when a new game is created
if hand_number == 0:
    st.session_state.last_sound_hand = 0
    st.session_state.flop_sound_hand = 0
    st.session_state.turn_sound_hand = 0
    st.session_state.river_sound_hand = 0

sound_file = None

# NEW HAND
if (hand_number > 0 and hand_number != st.session_state.last_sound_hand):
    sound_file = "deal.mp3"
    st.session_state.last_sound_hand = hand_number

# FLOP
elif (phase == "flop" and hand_number > 0 and hand_number != st.session_state.flop_sound_hand):
    sound_file = "deal.mp3"
    st.session_state.flop_sound_hand = hand_number

# TURN
elif (phase == "turn" and hand_number > 0 and hand_number != st.session_state.turn_sound_hand):
    sound_file = "deal.mp3"
    st.session_state.turn_sound_hand = hand_number

# RIVER
elif (phase == "river" and hand_number > 0 and hand_number != st.session_state.river_sound_hand):
    sound_file = "deal.mp3"
    st.session_state.river_sound_hand = hand_number

# IMPORTANT:
# Exactly ONE sound component exists on every rerun
play_sound(sound_file)

# -------------------------
# FIRST LINE + HOST BUTTONS
# -------------------------
col_first, col1, col2, col3 = (st.columns([2.5, 1, 1, 1]))
with col_first:
    st.markdown(f"""<div class="first-line">You are {player_name} ({player_id})</div>""",unsafe_allow_html=True)

# Hide host buttons visually for non-host
if not is_host:
    st.markdown("""<style>.st-key-deal_btn_box,.st-key-reset_btn_box,.st-key-forced_phase_box {visibility: hidden !important;}</style>""",unsafe_allow_html=True)

# -------------------------
# NEW HAND BUTTON
# -------------------------
with col1:
    with st.container(key="deal_btn_box"):
        deal_btn = st.button("New hand",disabled=not is_host)

# -------------------------
# NEW GAME BUTTON
# -------------------------
with col2:
    with st.container(key="reset_btn_box"):
        reset_btn = st.button("New game",disabled=not is_host)

# -------------------------
# FORCE PHASE BUTTON
# -------------------------
with col3:
    with st.container(
        key="forced_phase_box"):
        forced_phase_btn = st.button("Force A Phase",disabled=not is_host)

# -------------------------
# MAIN GAME AREA
# -------------------------
with st.container(key="below_first_line"):
    # -------------------------
    # GAME INFORMATION
    # -------------------------
    current_player = game_state.get("current_player")
    host_class = " host-game-info" if is_host else ""
    st.markdown(
        f"""
        <div class="game-info{host_class}">
            <b>Dealer:</b> {game_state.get('dealer')}
            &nbsp;&nbsp;|&nbsp;&nbsp;
            <b>Small Blind:</b> {game_state.get('small_blind')}
            &nbsp;&nbsp;|&nbsp;&nbsp;
            <b>Big Blind:</b> {game_state.get('big_blind')}
            &nbsp;&nbsp;|&nbsp;&nbsp;
            <b>Current Player:</b> {current_player}
            &nbsp;&nbsp;|&nbsp;&nbsp;
            <b>Phase:</b> {str(phase).capitalize()}
        </div>
        """,
        unsafe_allow_html=True)
    # -------------------------
    # TURN STATUS
    # -------------------------
    with st.container(key="status_area"):
        status_area = st.empty()
    is_my_turn = (player_id == current_player)
    disabled = not is_my_turn

# -------------------------
# HAND OVER
# -------------------------
if phase == "hand_over":
    overall_winner = game_state.get("overall_winner")
    winners = game_state.get("winners",[])
    # -----------------------------------------
    # OVERALL GAME WINNER
    # -----------------------------------------
    if overall_winner:
        winner_name = game_state["players"][overall_winner].get("name",overall_winner)
        # Look for the hand that won the final pot
        winning_hand = ""
        for pot in game_state.get("pots", []):
            if overall_winner in pot.get("winners", []):
                winning_hand = pot.get("winning_hand", "")
        # Display the final hand as well as the game winner
        if winning_hand:
            status_area.success(f"{winner_name} wins with {winning_hand} — and wins the game!")
        else:
            status_area.success(f"{winner_name} wins the game!")
        st.session_state.deal_next_hand = False
    # -----------------------------------------
    # NORMAL HAND OVER
    # -----------------------------------------
    elif winners:
        pots = game_state.get("pots", [])
        result_messages = []
        for pot in pots:
            pot_winners = pot.get("winners", [])
            winning_hand = pot.get("winning_hand", "")
            pot_name = pot.get("name", "Pot")
            pot_amount = pot.get("amount", 0)

            if not pot_winners:
                continue
            winner_names = [game_state["players"][pid].get("name", pid) for pid in pot_winners]
            names_text = " and ".join(winner_names)
            if winning_hand:
                result_messages.append(f"{pot_name} {pot_amount}: "f"{names_text} wins with {winning_hand}")
            else:
                result_messages.append(f"{pot_name} {pot_amount}: "f"{names_text} wins")
        if result_messages:
            status_area.success(" | ".join(result_messages))
        else:
            winner_names = [game_state["players"][pid].get("name", pid) for pid in winners]
            last_action = game_state.get("last_action", "")
            if last_action:
                status_area.success(f"{last_action} — Winner is {', '.join(winner_names)}")
            else:
                status_area.success("Winner(s): " + ", ".join(winner_names))
        # Pause so players can see the result
        time.sleep(3)
        # Host queues the next hand
        if is_host:
            st.session_state.deal_next_hand = True

# -------------------------
# AUTOMATIC TRANSITION
# -------------------------
elif phase == "awaiting_showdown":
    status_area.info("Determining winner...")
elif phase in ["awaiting_flop","awaiting_turn","awaiting_river"]:
    last_action = game_state.get("last_action", "")
    if last_action:
        status_area.info(f"{last_action} — Dealing...")
    else:
        status_area.info("Dealing...")

# -------------------------
# NORMAL PLAYER TURN
# -------------------------
elif is_my_turn:
    last_action = game_state.get("last_action", "")

    if last_action:
        status_area.success(f"{last_action} — It's your turn")
    else:
        status_area.success("It's your turn")

else:
    last_action = game_state.get("last_action", "")

    current_player_name = game_state["players"].get(current_player, {}).get("name", current_player)

    if last_action:
        status_area.info(f"{last_action} — Waiting for {current_player_name}")
    else:
        status_area.info(f"Waiting for {current_player_name}")

# -------------------------
# PLAYER STATE
# -------------------------
players_state = game_state.get("players",{})
max_bet = max((p["bet"] for p in players_state.values() if p["name"] != "" and not p["folded"]),default=0)
player_bet = (players_state[player_id]["bet"])
player_stack = (players_state[player_id]["stack"])

# -------------------------
# ACTION BUTTONS + TABLE
# -------------------------
col1, col2 = st.columns([3, 10])

# -------------------------
# ACTION BUTTONS
# -------------------------
with col1:
    # Disable player actions while the backend
    # is between betting streets.
    transition_phase = phase in ["awaiting_flop","awaiting_turn","awaiting_river","awaiting_showdown","hand_over",]
    action_disabled = (disabled or transition_phase or player_stack == 0)
    # Amount required to call
    to_call = max(0,min(max_bet - player_bet,player_stack))
    # -------------------------
    # FOLD
    # -------------------------
    fold_btn = st.button("Fold", disabled=(action_disabled or to_call == 0))
    # -------------------------
    # CHECK
    # -------------------------
    check_btn = st.button("Check", disabled=(action_disabled or to_call > 0))
    # -------------------------
    # CALL
    # -------------------------
    call_btn = st.button(f"Call {to_call}", disabled=(action_disabled or to_call == 0))
    # -------------------------
    # BET
    # -------------------------
    bet_amount = min(BIG_BLIND,player_stack)
    bet_btn = st.button(f"Bet {bet_amount}",key="openingbet",disabled=(action_disabled or max_bet > 0 or player_stack == 0))
    # -------------------------
    # RAISE-TO LOGIC
    # -------------------------
    raise_btn = False
    raiseto_amt = player_bet
    if max_bet > 0:
        min_raiseto = (max_bet + BIG_BLIND)
    else:
        min_raiseto = (BIG_BLIND)
    # Total amount player can have in pot
    max_raiseto = (player_stack + player_bet)
    # Clamp minimum to player's total capacity
    min_raiseto = min(min_raiseto,max_raiseto)
    raise_slider_col, raise_button_col = (st.columns([3, 1.6]))
    # -------------------------
    # NO LEGAL RAISE
    # -------------------------
    if (max_raiseto <= max_bet or max_raiseto <= player_bet or max_raiseto == 0):
        with raise_slider_col:
            st.write("")
        with raise_button_col:
            st.write("")
    # -------------------------
    # ALL-IN / SINGLE RAISE
    # -------------------------
    elif min_raiseto == max_raiseto:
        raiseto_amt = min_raiseto
        with raise_slider_col:
            st.write(f"Raise To: "f"{raiseto_amt}")
        with raise_button_col:
            st.write("")
            st.write("")
            raise_btn = st.button(f"Raise to {raiseto_amt}",disabled=action_disabled)
    # -------------------------
    # NORMAL RAISE SLIDER
    # -------------------------
    else:
        with raise_slider_col:
            raiseto_amt = st.slider("Raise To",min_value=min_raiseto,max_value=max_raiseto,step=BIG_BLIND,disabled=action_disabled)
        with raise_button_col:
            st.write("")
            st.write("")
            raise_btn = st.button(f"Raise to {raiseto_amt}",disabled=action_disabled)

# -------------------------
# TABLE
# -------------------------
with col2:
    table_area = st.empty()
    # ALWAYS draw current state first
    table_area.html(build_table_html(game_state))
    # ---------------------------------
    # AUTOMATIC PHASE TRANSITIONS
    # ---------------------------------
    # IMPORTANT: ONLY awaiting_* phases call/advance automatically. flop / turn / river are betting phases and MUST NOT be advancedhere.
    if phase in ["awaiting_flop","awaiting_turn","awaiting_river","awaiting_showdown"]:
        time.sleep(1)
        post(ADV_URL,{"expected_phase": phase})
        st.rerun()
    # -------------------------
    # DEAL NEXT HAND
    # -------------------------
    if (phase == "hand_over" and is_host and st.session_state.deal_next_hand):
        requests.post(DEAL_URL)
        st.session_state.deal_next_hand = False
        st.rerun()

# -------------------------
# ACTION LOGIC
# -------------------------
# FOLD
if fold_btn and is_my_turn:
    post(FOLD_URL,{"player_id":player_id})
    st.rerun()
# CHECK
if check_btn and is_my_turn:
    post(CHECK_URL,{"player_id":player_id})
    st.rerun()
# CALL
if call_btn and is_my_turn:
    post(CALL_URL,{"player_id":player_id})
    st.rerun()
# BET
if bet_btn and is_my_turn:
    post(BET_URL,{"player_id":player_id,"amount":bet_amount})
    st.rerun()
# RAISE
if (raise_btn and is_my_turn and raiseto_amt > max_bet):
    # Backend expects the amount to ADD, not the final total bet.
    amount_to_add = (int(raiseto_amt) - player_bet)
    post(RAISE_URL,{"player_id":player_id,"amount":amount_to_add})
    st.rerun()

# -------------------------
# HOST ACTION LOGIC
# -------------------------
if is_host:
    # NEW HAND
    if deal_btn:
        post(DEAL_URL)
        st.rerun()
    # NEW GAME
if reset_btn:
    post(RESET_URL)
    st.session_state.deal_next_hand = False
    st.session_state.last_sound_hand = 0
    st.session_state.flop_sound_hand = 0
    st.session_state.turn_sound_hand = 0
    st.session_state.river_sound_hand = 0
    st.rerun()
    # FORCE TEST PHASE
if forced_phase_btn:
    force_phase("preflop")
    st.rerun()
