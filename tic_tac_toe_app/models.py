from datetime import datetime,timedelta
from hashlib import md5
from sqlalchemy.orm import backref
from tic_tac_toe_app import db, login
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    #very usefull columns (not really)
    games_win_count = db.Column(db.Integer, index=True, default=0)
    games_lost_count = db.Column(db.Integer, index=True, default=0)

    administrator=db.Column(db.Boolean,default=False)

    def current_session(self):
        if(self.game_session==None):
            return None
        else:
            return self.game_session.code

    def has_session(self):
        if(self.game_session==None):
            return False
        else:
            return True     

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)

    def reset_game_session(self):
        """Deletes the current game session.
        
        Use this when the user did not log out and needs to kill the old session.
        """
        db.session.delete(self.game_session)
        db.session.commit()

    def get_id(self):
        """why?"""
        return self.id

    def serialize_info_for_client(self):
        """Return object data in serializeable format for unity client."""
        return {
            'GamesWon':self.games_win_count,
            'GamesLost':self.games_lost_count,
        } 

    def serialize(self):
        """Return object data in a serializeable format.
        
        Containts most of the object information, used for debug.
        """
        return {
            'username':self.username,
            'email':self.email,
            'password_hash':self.password_hash,
            'about_me':self.about_me,
            'last_seen':self.last_seen,
            'admin':self.administrator,
            'games_win':self.games_win_count,
            'games_lost':self.games_lost_count,
            'current_session':self.current_session()
        }


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class GameSession(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    code = db.Column(db.Integer,unique=True)

    user_id= db.Column(db.Integer,db.ForeignKey('user.id'))
    user = db.relationship("User",backref=backref("game_session",uselist=False))

    #only used when a guest is using the session
    last_message_timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    current_ongoing_game_id=db.Column(db.Integer,db.ForeignKey('game_room.id'))

    def get_current_game(self):
        if(self.current_game_room==None):
            return None
        else:
            return self.current_game_room.game_code

    def get_player_username(self):
        if(self.user==None):
            return None
        else:
            return self.user.username

    def get_user_data(self):
        if(self.user==None):
            return None
        else:
            return self.user.serialize_info_for_client()
    
    def get_last_message_timestamp(self):
        if(self.user==None):
            return self.last_message_timestamp
        else:
            return self.user.last_seen

    def set_last_message_timestamp(self,timestamp):
        if(self.user==None):
            self.last_message_timestamp=timestamp
        else:
            self.user.last_seen=timestamp
        return

    def serialize(self):
        """Return object data in a serializeable format.
        
        Containts most of the object information, used for debug.
        """
        return{
            'code':self.code,
            'user_id':self.user_id,
            'last_message_timestamp':self.get_last_message_timestamp(),
            'current_game':self.get_current_game(),
            'player_name':self.get_player_username()
        }

    def serialize_for_client(self):
        """Return object data in serializeable format for unity client."""
        return{
            'SessionCode':self.code,
            'SessionId':self.id,
            'CurrentGameCode':self.get_current_game(),
            'PlayerUsername':self.get_player_username(),
            'UserData':self.get_user_data()
        }


class GameRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    game_code = db.Column(db.Integer, index=True, unique=True)
    start_timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    is_game_joinable = db.Column(db.Boolean,default=True)
    
    players_sessions = db.relationship('GameSession',backref='current_game_room', lazy='dynamic')

    game_data = db.relationship("GameData",backref=backref('game_room',uselist=False),cascade="all,delete")
    game_data_id = db.Column(db.Integer,db.ForeignKey('game_data.id'))


    def get_elapsed_time(self, now=datetime.utcnow()):
        """Returns the amount of tima passed since its creation and the arg now."""
        then=self.start_timestamp
        duration=now-then
        return duration.seconds


    def get_players_count(self):
        """Returns the amount of current players."""
        my_length=len(self.players_sessions.all())
        return my_length


    def get_players_list(self):
        """Returns a list containing the sessions id of current players."""
        a=[]
        for i in self.players_sessions:
            a.append(i.code)
        return a


    #serialize for unity client
    def serialize_for_client(self):
        """Return object data in serializeable format for unity client."""
        return{
            'GameId':self.id,
            'GameCode':self.game_code,
            'PlayersId':self.get_players_list(),
            'SimpleData':self.game_data.serialize_for_client(),
        }

    #serializing all for debug purposes
    def serialize(self,now=datetime.utcnow()):
        """Return object data in a serializeable format.
        
        Containts most of the object information, used for debug.
        """
        return{
            'id':self.id,
            'game_code':self.game_code,
            'start_timestamp':self.start_timestamp,
            'players_amount':self.get_players_count(),
            'players':self.get_players_list(),
            'is_game_joinable':self.is_game_joinable,
            'game_data':self.game_data.serialize(),
            'time_elapsed_seconds':self.get_elapsed_time(now)
        }

    
class GameData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    #the winner column hold the session code of the winner, -1 it means it does not have one
    winner = db.Column(db.Integer,default=-1)
    #thi is the client that can move
    current_moving_session = db.Column(db.Integer)
    '''
    a0 is the top left cell, a2 is the top right cell, c0 is the bottom left, c2 is the bottom right and so on 
    the cells columns hold the number of the session that has claimed the cell, -1 if the cell is not held by a session
    could have been a simple string holding a list of values since i still need to make a list of the cells to send at the client (see get_cells())
    '''
    a0 = db.Column(db.Integer,default=-1)
    a1 = db.Column(db.Integer,default=-1)
    a2 = db.Column(db.Integer,default=-1)

    b0 = db.Column(db.Integer,default=-1)
    b1 = db.Column(db.Integer,default=-1)
    b2 = db.Column(db.Integer,default=-1)

    c0 = db.Column(db.Integer,default=-1)
    c1 = db.Column(db.Integer,default=-1)
    c2 = db.Column(db.Integer,default=-1)


    def get_cells(self):
        """Get a list of the cells."""
        cells=[]

        cells.append(self.a0)
        cells.append(self.a1)
        cells.append(self.a2)

        cells.append(self.b0)
        cells.append(self.b1)
        cells.append(self.b2)

        cells.append(self.c0)
        cells.append(self.c1)
        cells.append(self.c2)
        
        return cells


    def change_current_player(self):
        """Switch turn."""
        #cant change player if the game is joinable since there is only one
        if(not self.game_room.is_game_joinable):
            #getting list of player sessions id
            players_in_game =self.game_room.get_players_list()
            #since a game is not joinable when there two players in, get a list copying the session code and eclude the current moving player
            players_in_game.remove(self.current_moving_session)
            self.current_moving_session=players_in_game[0]


    def get_cell_value_by_index(self,index):
        if  8>=index>=0:
            cells=self.get_cells()
            return cells[index]
        else:
            return None
            
    
    def set_cell_value_by_index(self,index,value):
        if  8>=index>=0:

            if(index==0):
                self.a0=value
            elif(index==1):
                self.a1=value
            elif(index==2):
                self.a2=value
                
            elif(index==3):
                self.b0=value
            elif(index==4):
                self.b1=value
            elif(index==5):
                self.b2=value

            elif(index==6):
                self.c0=value
            elif(index==7):
                self.c1=value
            elif(index==8):
                self.c2=value
        
        else:
            return -1


    def check_winning_condition(self):
        """Checks the cell for a winning condition.

        Check if a player has claimed a row/diagonal/column for himself and change, in the game data, the winner if a match occurs
        """

        #for some reason i could not compare a in to self.winner so i used this workaround
        if(str(self.winner)!= str(-1)):
            #if there is a winner it's not necessary to check winning conditions
            return
        
        #if a0 is held by a session i need to check the colum 0 and the row a
        if(self.a0!=-1):
            #checking the a row
            if(self.a0==self.a1==self.a2):
                self.winner=self.a0
            #checking the 0 column
            if(self.a0==self.b0==self.c0):
                self.winner=self.a0

        #if b1, the cell at the center of the grid is held, i need to check the b row the 1 column and the 2 diagonals pasing trough b1
        if(self.b1!=-1):
            #checing the b row
            if(self.b0==self.b1==self.b2):
                self.winner=self.b1

            #checking the top left to bottom right diagonal
            if(self.a0==self.b1==self.c2):
                self.winner=self.b1

            #checking the top right to bottom left diagonal
            if(self.a2==self.b1==self.c0):
                self.winner=self.b1

            #checking the 1 column
            if(self.a1==self.b1==self.c1):
                self.winner=self.b1

        #if c2 is held by a session i need to check the column 2 and the row c
        if(self.c2!=-1):
            #checking the c row
            if(self.c0==self.c1==self.c2):
                self.winner=self.c2

            #checking the 2 column
            if(self.a2==self.b2==self.c2):
                self.winner=self.c2


    def serialize_for_client(self):
        """Return object data in serializeable format for unity client."""
        return {
            'Winner':self.winner,
            'CurrentSessionId':self.current_moving_session,
            'Cells':self.get_cells()
        }


    def serialize(self):
        """Return object data in a serializeable format.
        
        Containts most of the object information, used for debug.
        """
        return {
            'data_id': self.id,
            'winner':self.winner,
            'cells':self.get_cells(),
            'field_a0':self.a0,
            'field_a1':self.a1,
            'field_a2':self.a2,

            'field_b0':self.b0,
            'field_b1':self.b1,
            'field_b2':self.b2,

            'field_c0':self.c0,
            'field_c1':self.c1,
            'field_c2':self.c2
        }
