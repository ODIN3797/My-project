"""Only synthetic CDR placeholders, for deterministic timing demonstration."""
from __future__ import annotations
from pathlib import Path
import sqlite3

T0=1_740_000_010_000_000_000

def make(path:Path, segments:list[tuple[int,int]]) -> Path:
    path=Path(path); path.parent.mkdir(exist_ok=True,parents=True)
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE topics (id INTEGER PRIMARY KEY,name TEXT,type TEXT,serialization_format TEXT,offered_qos_profiles TEXT); CREATE TABLE messages (id INTEGER PRIMARY KEY, topic_id INTEGER, timestamp INTEGER, data BLOB);')
        db.execute("INSERT INTO topics VALUES(1,'/robot/cmd_vel','geometry_msgs/msg/Twist','cdr','')")
        db.execute("INSERT INTO topics VALUES(2,'/robot/scan','sensor_msgs/msg/LaserScan','cdr','')")
        ix=0;now=T0
        for duration,hz in segments:
            for t in range(duration*hz):
                ix+=1;db.execute('INSERT INTO messages VALUES(?,?,?,?)',(ix,1,now+(t*1_000_000_000)//hz,b'\x00\x01\x00\x00'))
            now+=duration*1_000_000_000
        for i in range(120):
            ix+=1;db.execute('INSERT INTO messages VALUES(?,?,?,?)',(ix,2,T0+i*1_000_000_000//6,b'\x00\x01\x00\x00'))
    return path

if __name__=='__main__':
    root=Path('demo_rate_data')
    print(make(root/'fictional_reference.db3',[(20,20)]))
    print(make(root/'fictional_rate_shift.db3',[(11,20),(6,165),(3,20)]))
