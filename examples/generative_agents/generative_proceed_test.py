
import redis
import sys
from generative_agent_new import GenerativeAgent
import json
from ville import TheVille
env = TheVille()

# start_time = datetime.datetime(2021, 1, 1, 8, 0, 0)
# time_delta = timedelta(minutes=10)

# time_per_step = 10
# time_dict = json.dumps({"start_time": str(start_time), "time_per_step": str(time_per_step)})
# with open("assets/time.json","w") as outfile:
#     outfile.write(time_dict)
# with open("assets/time.json") as outfile:
#     time_dict = json.load(outfile)

with open("assets/personas/n25_iss.json") as f:
    personas = json.load(f)
    for key, value in personas.items():
        dict = personas[key]
        dict["retention"] = 5
with open("assets/personas/new_n25_iss.json", "w") as f:
    resutl_dict = json.dumps(personas)
    f.write(resutl_dict)
# with open("assets/personas/new_n25_iss.json") as f:
#     personas = json.load(f)
#     for key, value in personas.items():
#         dict = personas[key]
#         print(dict["retention"])
persona_dict = {}
for p, v in personas.items():
    persona_dict[p] = GenerativeAgent(p, 0, env)
i = 0
step = 10000
for i in range(0, step):
    j = 0
    for j,p in enumerate(persona_dict.items()):
        # perceived = persona.perceive()
        name, persona = p
        if j < 3:
        # retrived = persona.retrieve(perceived)
        # result = persona.plan(persona_dict,"First day",retrived)
            if i == 0:
                planned = persona.proceed(persona_dict,"First day")
            else:
                planned = persona.proceed(persona_dict,None)
            persona.step += 1
        else:
            break
        j += 1

#     planned = persona.plan(retrived)


