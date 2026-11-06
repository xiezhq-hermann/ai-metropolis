# Term
## Smem
KeYID : s_mem:<persona_name>:<obj_count>
value:<obj_id>
Here I use redis sorted set for events to better organize the key and values 
## For cursor or event number
To avoid use `scan_iter`, I store them in db.
Key ID: <persona_name>:event_count, <persona_name>:chat_count, <persona_name>:thought_count

## Scratch: storing patterns and constants of persona
New_key_id : Scratch:<persona_name>:<item>
Time Scratch:Ben:7
At each time I fetch them from db and get into memory for efficiency.
## s_mem spatial memory
I use sorted set to manage s_mem
New_key_id : s_mem:<persona_name>
event_id : <event_number>
```
mapping = {"subject":self.subject, "predicate":self.predicate, "object":self.object, "location":self.location, "description":self.description, "present":self.present, "step":self.step}
```
## a_mem associate memory
Add time stamp for sorting.

New_key_id : a_mem:<persona_name>:type:<id>
id
one sorted set for event/chat/thought
example a_mem:Ben:chat:1 
Three types: chat, thought, event
## kw_strength
New issue: 
KEY_ID : <persona_name>_kw_strength_< kw >

## GenerativeEvent
add present, self.p to this class to show whether this obj is presented

### new issue
embedding
映射step和真实时间，360 step -> 1h
关键词索引，relational database
### arch
perceieve, retrieve,plan, reflect -> agent,env
内存——> chatgpt, db -> 内存 -> chatgpt
how to store embedding into redis db