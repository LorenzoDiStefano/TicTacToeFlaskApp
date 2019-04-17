from datetime import datetime
from flask import request
from tic_tac_toe_app import app, db
from tic_tac_toe_app.models import User, GameRoom, GameData, GameSession
from flask import Flask, jsonify
import random,json
from sqlalchemy import or_


class Payload(object):
    """Class for deserializing unity client post requests data."""
    def __init__(self, j):
        self.__dict__ = json.loads(j)


def create_session(requesting_user=None):
    """Creates a session for requesting user/guest."""
    if(requesting_user!=None):
        #check if requesting user already has a session
        if(requesting_user.has_session()):
            return None
    while(True):
        #generating a random code for a new session
        new_game_session_code = random.randint(0,0xfffffff)
        #triying to get a session with the new generated code with a query
        real_game_session = GameSession.query.filter_by(code=new_game_session_code).first()
        #checking the query result, if it's not none a game with that code already exist
        if(real_game_session==None):
            #if it does not, create a new session and commit changes to the database
            new_game_session = GameSession(code=new_game_session_code,user=requesting_user)
            db.session.add(new_game_session)
            db.session.commit()
            return new_game_session.serialize_for_client()


def create_game_api(requesting_session):
    """Create a game for the requesting session"""
    while(True):
        #generate a random value to use as code
        value = random.randint(0,0xfffffff)
        #checking if a game room with that code already exists
        game = GameRoom.query.filter_by(game_code=value).first()
        if(game==None):
            #if it doesn't exist, create one
            new_game = GameRoom(game_code=value)
            new_game.game_data = GameData()
            requesting_session.current_game_room = new_game
            #setting the first player to move to be the requesting session
            new_game.game_data.current_moving_session = requesting_session.code
            db.session.add(new_game)
            db.session.commit()
            return new_game.serialize_for_client()


# this route is used for receiving a move from the client and sending the game data back to it, the client can send -1 in the field CellToTake and just get back the updated data
@app.route('/api_send_move',methods=['POST'])
def api_send_move():

    #getting data from post request
    jsondata = Payload(request.form["payload"])

    session_id = jsondata.SessionId
    session_code = jsondata.SessionCode
    cell_to_take_index = jsondata.CellToTake

    #getting current game data info using the session id and code
    current_game_data = GameSession.query.get(int(session_id)).current_game_room.game_data

    #checking if the game already has a winner and if the cell to take is -1, it if's -1 just send back the game data
    if(str(current_game_data.winner)==str(-1) and cell_to_take_index!=-1):
        #checking if the client can make a move
        if(current_game_data.current_moving_session==session_code):
            current_cell_value = current_game_data.get_cell_value_by_index(cell_to_take_index)
            if(current_cell_value==-1):
                current_game_data.set_cell_value_by_index(cell_to_take_index,session_code)
                current_game_data.check_winning_condition()
                current_game_data.change_current_player()
                db.session.commit()

    ongoing_game = current_game_data.game_room

    return jsonify(ongoing_game.serialize_for_client())
    

@app.route('/api_leave_game',methods=['POST'])
def api_leave_game():
    outcome="error"

    #getting data from post request
    jsondata = Payload(request.form["payload"])
    session_id = jsondata.SessionId
    session_code = jsondata.SessionCode

    #query to get the session that is asking to leave the game
    session_to_close = GameSession.query.get(int(session_id))

    #if the session exists and the session code is equal to the given session code continue, the session code check is for a bit of safety
    if(session_to_close!=None and session_to_close.code==session_code):
        #check if the session is in a gameroom
        room_to_leave = session_to_close.current_game_room
        if(room_to_leave!=None):

            if(room_to_leave.get_players_count()==1 ):
                #if ther is only one player, so the requesting session just delete the room
                db.session.delete(room_to_leave)
            else:
                #if there is another player, get his code
                players_in_game = room_to_leave.get_players_list()
                players_in_game.remove(session_code)
                winner = room_to_leave.game_data.winner
                #if there is not a winner, the remaming player wins
                if(str(winner)==str(-1)):
                    session_to_close.current_game_room.game_data.winner=players_in_game[0]
            
            #leaving the game anyway
            session_to_close.current_game_room = None
            db.session.commit()
            outcome = "succes"
    
    return jsonify(outcome)


@app.route('/api_join_matchmaking',methods=['POST'])
def join_matchmaking():
    #inistializing response from server
    response={
        "Game":None,
        "Outcome":False,
        "Message":""
    }

    #deserializing payload infos
    jsondata = Payload(request.form["payload"])

    session_id = jsondata.SessionId
    session_code = jsondata.SessionCode

    requesting_session = GameSession.query.get(int(session_id))

    if(requesting_session==None):
        return jsonify("session does not exist")

    if(requesting_session.code!=session_code):
        return jsonify("error")

    if(requesting_session.current_game_room!=None):
        return jsonify("session already has a game")

    #query all the game rooms
    game_rooms = GameRoom.query.all()
    now = datetime.utcnow()

    #getting the serialized info of the rooms that can be joined, it can be done with a single query
    serializedList = [info.serialize(now) for info in game_rooms if info.is_game_joinable==True]

    #this hould not be needed anyway, doing this for safety
    acceptable_games_dict = [acceptable for acceptable in serializedList if acceptable["players_amount"] <2]

    if(len(acceptable_games_dict)!=0):

        #if there is a game, take the first one
        free_game = acceptable_games_dict[0]
        #querying the db object
        referenced_game = GameRoom.query.get(int(free_game['id']))

        #if there is already one player make the game not joinable since a second is joining
        if(free_game['players_amount']==1):
            referenced_game.is_game_joinable = False
        
        requesting_session.current_game_room=referenced_game

        response["Outcome"] = True
        response["Game"] = referenced_game.serialize_for_client()
        db.session.commit()
    else:
        #if there are not game just create one
        response["Outcome"] = True
        response["Game"] = create_game_api(requesting_session)

    return jsonify(response)


#server status check
@app.route('/api_tok_tok')
def api_tok_tok():
    response={
        "Status":True
    }
    return jsonify(response)


#login function for login of registred users and guests
@app.route('/api_login', methods=['POST'])
def api_login_user():
    #initializing server response
    response={
        "Session":None,
        "Outcome":True,
        "Message":""
    }

    #extracting object from request payload
    jsondata = Payload(request.form["payload"])
    #if it is not a guest check try to log in user
    if(not jsondata.IsGuest):
        #extracting common used data to write less
        username = jsondata.LoginUsername
        password = jsondata.LoginPassword
        need_reset = jsondata.NeedReset
        #query for a user with the provided username
        user = User.query.filter_by(username=username).first()
        #checking if user exist and if the password provided by the request is legit
        if(user!=None and user.check_password(password)):
            response["Message"]+="logging in user."
            #boolean for keeping track of need top create a session for the user
            need_new_session = True
            if(user.has_session()):
                response["Message"]+="user already has session."
                if(need_reset):
                    response["Message"]+="resetting user session."
                    user.reset_game_session()
                else:
                    need_new_session = False
            #if the useer needs a new session it gets created and sended with the response
            if(need_new_session):
                response["Session"] = create_session(user)
        else:
            response["Outcome"] = False
            response["Message"]+="login error."
    #else create a session for a guest
    else:
        response["Message"]+="created new session for guest."
        response["Session"] = create_session()

    return jsonify(response)


@app.route('/api_logout',methods=['POST'])
def api_logout_user():
    outcome = "succes"

    #getting data from request
    jsondata = Payload(request.form["payload"])
    sessionId = jsondata.SessionId
    sessionCode = jsondata.SessionCode

    #getting session requesting logout
    session_to_close = GameSession.query.get(int(sessionId))
    if(session_to_close!=None and session_to_close.code==sessionCode):
        #deleting session
        db.session.delete(session_to_close)
        db.session.commit()
    else:
        outcome = "error"

    return jsonify(outcome)