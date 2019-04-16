from datetime import datetime
from flask_login import current_user, login_required
from tic_tac_toe_app import app, db
from tic_tac_toe_app.models import User,GameRoom,GameData,GameSession
from flask import Flask, jsonify


#Look Data
@app.route("/query_game_rooms")
def query_game_rooms():
    data=GameRoom.query.all()
    comprehension_dict={c_data.id:c_data.serialize(datetime.utcnow()) for c_data in data}
    return jsonify(comprehension_dict)


@app.route("/query_games_data")
def query_games_data():
    data=GameData.query.all()
    comprehension_dict={c_data.id:c_data.serialize() for c_data in data}
    return jsonify(comprehension_dict)


@app.route("/query_users")
def query_users():
    data=User.query.all()
    comprehension_dict={c_data.id:c_data.serialize() for c_data in data}
    return jsonify(comprehension_dict)


@app.route("/query_game_sessions")
def query_game_sessions():
    data=GameSession.query.all()
    comprehension_dict={c_data.id:c_data.serialize() for c_data in data}
    return jsonify(comprehension_dict)


#Delete data
@app.route("/delete_game_rooms")
@login_required
def delete_game_rooms():
    # if(current_user.administrator==False):
    #     return jsonify("acces denied")
    ongoing= db.session.query(GameRoom)
    for i in ongoing:
        # must be delete rooms one by one or it will leave game data connected to them
        db.session.delete(i)
    db.session.commit()
    return jsonify("deleted all")


@app.route("/delete_game_sessions")
@login_required
def delete_game_sessions():
    # if(current_user.administrator==False):
    #     return jsonify("acces denied")
    ongoing= db.session.query(GameSession)
    for i in ongoing:
        db.session.delete(i) 
    db.session.commit()
    return jsonify("deleted all sessions")


@app.route("/delete_users")
@login_required
def delete_users():
    # if(current_user.administrator==False):
    #     return jsonify("acces denied")
    db.session.query(User).delete()
    db.session.commit()
    return jsonify("deleted all users")


#debug route for creating a hollow game room
@app.route("/debug_create_game_room")
def debug_create_game_room():
    while(True):
        value= random.randint(0,0xfffffff)
        game = GameRoom.query.filter_by(game_code=value).first()
        if(game==None):
            new_game=GameRoom(game_code=value)
            if(current_user.is_authenticated):
                new_game.player_one=current_user
            new_game.game_data= GameData()
            db.session.add(new_game)
            db.session.commit()
            return jsonify(new_game.game_code)