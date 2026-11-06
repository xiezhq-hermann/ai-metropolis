import os
import sys
import json
import redis


def dump_db(r, filename='data.json'):
    keys = r.keys('*')
    keys = [
        key for key in keys if not key.startswith("recorded_movement:") and not key.startswith("recorded_calls:") and
        not key.startswith("grid:")
    ]

    pipe = r.pipeline()
    for key in keys:
        pipe.type(key)
    types = pipe.execute()

    # Another round of pipelined commands based on type
    for key, type in zip(keys, types):
        if type == 'string':
            pipe.get(key)
        elif type == 'hash':
            pipe.hgetall(key)
        elif type == 'zset':
            pipe.zrange(key, 0, -1, withscores=True)
        elif type == 'set':
            pipe.smembers(key)
        else:
            print(f"Unsupported type: {type} for key: {key}")
    values = pipe.execute()

    data = {}
    # Process fetched data
    for key, type, value in zip(keys, types, values):
        if type == 'string':
            data[key] = value
        elif type == 'hash':
            data[key] = value
        elif type == 'zset':
            if key.startswith("geo:"):
                # Additional pipelining for geopositions
                geo_pipe = r.pipeline()
                for member, _ in value:
                    geo_pipe.geopos(key, member)
                positions = geo_pipe.execute()
                data[key] = dict(zip([member for member, _ in value], positions))
            else:
                print(f"Unsupported type: {type} for key: {key}")
        elif type == 'set':
            data[key] = list(value)
        else:
            print(f"Unsupported type: {type} for key: {key}")
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)


def clear_all_db():
    env_db = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    mem_db = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    trace_db = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
    env_db.flushdb()
    mem_db.flushdb()
    trace_db.flushdb()


def dump_all_db(setting):
    env_db = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    trace_db = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
    if not os.path.exists(setting):
        os.mkdir(setting)
    setting += '/'

    dump_db(env_db, setting + 'env_db.json')
    dump_db(trace_db, setting + 'trace_db.json')


def reuse_env(r):
    keys = [
        key for key in r.keys('*') if not key.startswith("recorded_movement:") and
        not key.startswith("recorded_calls:") and not key.startswith("grid:")
    ]

    pipe = r.pipeline()
    for key in keys:
        pipe.delete(key)
    for key in r.keys('grid:*'):
        pipe.hdel(key, 'personas')
    pipe.execute()


if __name__ == '__main__':
    # todo, a more organized way to handle arguments
    flush = True if len(sys.argv) > 1 and sys.argv[1] == 'flush' else False
    reuse = True if len(sys.argv) > 1 and sys.argv[1] == 'reuse' else False
    new_directory = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] not in ["flush", "reuse"] else ""
    if new_directory:
        if not os.path.exists(new_directory):
            os.mkdir(new_directory)
        new_directory += '/'
    env_db = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    mem_db = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    trace_db = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
    if flush:
        env_db.flushdb()
        mem_db.flushdb()
        trace_db.flushdb()
    elif reuse:
        reuse_env(env_db)
        trace_db.flushdb()
    else:
        dump_db(env_db, new_directory + 'env_db.json')
        # dump_db(mem_db, new_directory + 'mem_db.json')
        dump_db(trace_db, new_directory + 'trace_db.json')
