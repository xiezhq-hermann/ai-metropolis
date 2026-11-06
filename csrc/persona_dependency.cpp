#include <hiredis/hiredis.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <future>
#include <iostream>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace py = pybind11;

#define INSTRUMENTATION_ENABLED false
#define CORRECTNESS_CHECK_ENABLED false

#define CORRECTNESS_CHECK(expr, msg)   \
  {                                    \
    if (CORRECTNESS_CHECK_ENABLED) {   \
      if (!(expr)) {                   \
        throw std::runtime_error(msg); \
      }                                \
    }                                  \
  }

std::vector<std::string> split(const std::string &str, char delimiter) {
  std::vector<std::string> tokens;
  std::string token;
  std::stringstream ss(str);

  while (std::getline(ss, token, delimiter)) {
    tokens.push_back(token);
  }

  return tokens;
}

std::unordered_set<std::string> set_difference(
    const std::unordered_set<std::string> &set1,
    const std::unordered_set<std::string> &set2) {
  std::unordered_set<std::string> result;
  for (const auto &elem : set1) {
    if (set2.find(elem) == set2.end()) {
      result.insert(elem);
    }
  }
  return result;
}

class RedisClient {
 public:
  RedisClient(const std::string &host, int port, int db = 0) {
    context = redisConnect(host.c_str(), port);
    if (context == NULL || context->err) {
      if (context) {
        throw std::runtime_error("Redis connection error: " +
                                 std::string(context->errstr));
      } else {
        throw std::runtime_error(
            "Redis connection error: can't allocate redis context");
      }
    }
    // Select the database
    redisReply *reply = (redisReply *)redisCommand(context, "SELECT %d", db);
    if (reply == NULL || context->err) {
      if (context) {
        throw std::runtime_error("Redis SELECT command error: " +
                                 std::string(context->errstr));
      } else {
        throw std::runtime_error(
            "Redis SELECT command error: can't allocate redis context");
      }
    }
    freeReplyObject(reply);
  }

  ~RedisClient() {
    if (context != NULL) {
      redisFree(context);
    }
  }

  void set_int(const std::string &key, int value) {
    redisReply *reply =
        (redisReply *)redisCommand(context, "SET %s %d", key.c_str(), value);
    freeReplyObject(reply);
  }

  std::string get(const std::string &key) const {
    redisReply *reply =
        (redisReply *)redisCommand(context, "GET %s", key.c_str());
    if (reply == NULL) {
      throw std::runtime_error("Redis GET command failed");
    }
    std::string value = reply->str ? reply->str : "";
    freeReplyObject(reply);
    return value;
  }

  std::string hget(const std::string &key, const std::string &field) const {
    redisReply *reply = (redisReply *)redisCommand(context, "HGET %s %s",
                                                   key.c_str(), field.c_str());
    if (reply == NULL) {
      throw std::runtime_error("Redis HGET command failed");
    }
    std::string value = reply->str ? reply->str : "";
    freeReplyObject(reply);
    return value;
  }

  void hset(const std::string &key, const std::string &field,
            const std::string &value) {
    redisReply *reply = (redisReply *)redisCommand(
        context, "HSET %s %s %s", key.c_str(), field.c_str(), value.c_str());
    freeReplyObject(reply);
  }

  std::vector<std::string> pipeline_hget(const std::vector<std::string> &keys,
                                         const std::string &field) const {
    for (const auto &key : keys) {
      redisAppendCommand(context, "HGET %s %s", key.c_str(), field.c_str());
    }

    std::vector<std::string> results;
    for (size_t i = 0; i < keys.size(); ++i) {
      redisReply *reply;
      if (redisGetReply(context, (void **)&reply) != REDIS_OK) {
        throw std::runtime_error("Redis HGET pipeline command failed");
      }
      std::string value = reply->str ? reply->str : "";
      results.push_back(value);
      freeReplyObject(reply);
    }

    return results;
  }

  void pipeline_hset(const std::vector<std::string> &keys,
                     const std::string &field, const std::string &value) {
    for (const auto &key : keys) {
      redisAppendCommand(context, "HSET %s %s %s", key.c_str(), field.c_str(),
                         value.c_str());
    }

    for (const auto &key : keys) {
      redisReply *reply;
      if (redisGetReply(context, (void **)&reply) != REDIS_OK) {
        throw std::runtime_error("Redis HSET pipeline command failed");
      }
      freeReplyObject(reply);
    }
  }

  void watch(const std::string &key) {
    redisReply *reply =
        (redisReply *)redisCommand(context, "WATCH %s", key.c_str());
    if (reply == NULL) {
      throw std::runtime_error("Redis WATCH command failed");
    }
    freeReplyObject(reply);
  }

  void multi() {
    redisReply *reply = (redisReply *)redisCommand(context, "MULTI");
    if (reply == NULL) {
      throw std::runtime_error("Redis MULTI command failed");
    }
    freeReplyObject(reply);
  }

  void exec() {
    redisReply *reply = (redisReply *)redisCommand(context, "EXEC");
    if (reply == nullptr || reply->type == REDIS_REPLY_ERROR) {
      throw std::runtime_error("Redis EXEC command failed");
    }
    if (reply->type == REDIS_REPLY_NIL) {
      throw std::runtime_error("Transaction aborted due to changes");
    }
    // else {
    //   std::cout << "Transaction executed successfully" << std::endl;
    // }
    freeReplyObject(reply);
  }

  void sadd(const std::string &key, const std::string &member) {
    redisReply *reply = (redisReply *)redisCommand(context, "SADD %s %s",
                                                   key.c_str(), member.c_str());
    if (reply == NULL) {
      throw std::runtime_error("Redis SADD command failed");
    }
    freeReplyObject(reply);
  }

  void srem(const std::string &key, const std::string &member) {
    redisReply *reply = (redisReply *)redisCommand(context, "SREM %s %s",
                                                   key.c_str(), member.c_str());
    if (reply == NULL) {
      throw std::runtime_error("Redis SREM command failed");
    }
    freeReplyObject(reply);
  }

  void add_dependency(const std::string &persona_name,
                      const std::string &blocking) {
    sadd("persona:" + persona_name + ":blocking", blocking);
    sadd("persona:" + blocking + ":blocked", persona_name);
  }

  void remove_dependency(const std::string &persona_name,
                         const std::string &blocking) {
    srem("persona:" + persona_name + ":blocking", blocking);
    srem("persona:" + blocking + ":blocked", persona_name);
  }

  std::unordered_set<std::string> smembers(const std::string &key) const {
    redisReply *reply =
        (redisReply *)redisCommand(context, "SMEMBERS %s", key.c_str());
    if (reply == NULL) {
      throw std::runtime_error("Redis SMEMBERS command failed");
    }
    std::unordered_set<std::string> members;
    for (size_t i = 0; i < reply->elements; ++i) {
      members.insert(reply->element[i]->str);
    }
    freeReplyObject(reply);
    return members;
  }

  std::vector<bool> pipeline_dep_check(
      const std::vector<std::string> &persona_names) {
    for (const auto &persona_name : persona_names) {
      auto key = "persona:" + persona_name + ":blocked";
      redisAppendCommand(context, "SMEMBERS %s", key.c_str());
    }

    std::vector<bool> results;
    for (size_t i = 0; i < persona_names.size(); ++i) {
      redisReply *reply;
      if (redisGetReply(context, (void **)&reply) != REDIS_OK) {
        throw std::runtime_error("Redis SMEMBERS pipeline command failed");
      }
      bool ready = reply->elements == 0;
      results.push_back(ready);
      freeReplyObject(reply);
    }
    return results;
  }

  std::vector<bool> pipeline_oracle_dep_check(
      const std::vector<std::string> &persona_names) {
    std::vector<std::string> step_keys;
    for (const auto &persona_name : persona_names) {
      step_keys.push_back("persona:" + persona_name);
    }
    std::vector<std::string> steps = pipeline_hget(step_keys, "step");
    for (size_t i = 0; i < persona_names.size(); ++i) {
      auto key =
          "oracle_dependency_current:" + persona_names[i] + ":" + steps[i];
      redisAppendCommand(context, "SMEMBERS %s", key.c_str());
    }

    std::vector<bool> results;
    for (size_t i = 0; i < persona_names.size(); ++i) {
      redisReply *reply;
      if (redisGetReply(context, (void **)&reply) != REDIS_OK) {
        throw std::runtime_error("Redis SMEMBERS pipeline command failed");
      }
      bool ready = reply->elements == 0;
      results.push_back(ready);
      freeReplyObject(reply);
    }
    return results;
  }

 private:
  redisContext *context;
};

class RedisClientPool {
 public:
  RedisClientPool(const std::string &host, int port, int db, int pool_size = 10)
      : host(host), port(port), db(db), pool_size(pool_size) {
    for (int i = 0; i < pool_size; ++i) {
      clients.push_back(new RedisClient(host, port, db));
    }
  }

  ~RedisClientPool() {
    for (auto client : clients) {
      delete client;
    }
  }

  RedisClient *get_client() {
    std::lock_guard<std::mutex> lock(mutex);
    if (clients.empty()) {
      throw std::runtime_error("Redis client pool is empty");
    }
    RedisClient *client = clients.back();
    clients.pop_back();
    return client;
  }

  void release_client(RedisClient *client) {
    std::lock_guard<std::mutex> lock(mutex);
    clients.push_back(client);
  }

  void set_int(const std::string &key, int value) {
    RedisClient *client = get_client();
    client->set_int(key, value);
    release_client(client);
  }

  std::string get(const std::string &key) {
    RedisClient *client = get_client();
    std::string value = client->get(key);
    release_client(client);
    return value;
  }

  std::string hget(const std::string &key, const std::string &field) {
    RedisClient *client = get_client();
    std::string value = client->hget(key, field);
    release_client(client);
    return value;
  }

  void hset(const std::string &key, const std::string &field,
            const std::string &value) {
    RedisClient *client = get_client();
    client->hset(key, field, value);
    release_client(client);
  }

  std::vector<std::string> pipeline_hget(const std::vector<std::string> &keys,
                                         const std::string &field) {
    RedisClient *client = get_client();
    std::vector<std::string> results = client->pipeline_hget(keys, field);
    release_client(client);
    return results;
  }

  std::unordered_set<std::string> smembers(const std::string &key) {
    RedisClient *client = get_client();
    std::unordered_set<std::string> members = client->smembers(key);
    release_client(client);
    return members;
  }

  std::vector<bool> pipeline_dep_check(
      const std::vector<std::string> &persona_names) {
    RedisClient *client = get_client();
    std::vector<bool> results = client->pipeline_dep_check(persona_names);
    release_client(client);
    return results;
  }

 private:
  std::string host;
  int port;
  int db;
  int pool_size;
  std::vector<RedisClient *> clients;
  std::mutex mutex;
};

enum class Instrumentation {
  Start,
  LoopStart,
  GeoQuery,
  AvailabilityCheck,
  UpdatingTaskQueue,
  UpdatingAgentStatus,
  End,
  DepStart,
  DepLoopStart,
  DepGeoQuery,
  DepCalculating,
  DepUpdatingDep,
  DepUpdatingAgentStatus,
  DepEnd
};

const char *instrumentation_to_string(Instrumentation instr) {
  switch (instr) {
    case Instrumentation::Start:
      return "Start";
    case Instrumentation::LoopStart:
      return "LoopStart";
    case Instrumentation::GeoQuery:
      return "GeoQuery";
    case Instrumentation::AvailabilityCheck:
      return "AvailabilityCheck";
    case Instrumentation::UpdatingTaskQueue:
      return "UpdatingTaskQueue";
    case Instrumentation::UpdatingAgentStatus:
      return "UpdatingAgentStatus";
    case Instrumentation::End:
      return "End";
    case Instrumentation::DepStart:
      return "DepStart";
    case Instrumentation::DepLoopStart:
      return "DepLoopStart";
    case Instrumentation::DepGeoQuery:
      return "DepGeoQuery";
    case Instrumentation::DepCalculating:
      return "DepCalculating";
    case Instrumentation::DepUpdatingDep:
      return "DepUpdatingDep";
    case Instrumentation::DepUpdatingAgentStatus:
      return "DepUpdatingAgentStatus";
    case Instrumentation::DepEnd:
      return "DepEnd";
  }
}

class PersonaDependency {
 public:
  struct DependencyInfo {
    std::unordered_set<std::string> blocking;
    std::unordered_set<std::string> blocked;
  };

  PersonaDependency(const std::vector<std::string> &persona_names,
                    int agent_vision_radius, const std::string &redis_host,
                    int redis_port, int db)
      : agent_vision_radius(agent_vision_radius),
        redis_client_updating(redis_host, redis_port, db),
        redis_client_clustering(redis_host, redis_port, db),
        redis_client_pool(redis_host, redis_port, db) {
    for (const auto &name : persona_names) {
      persona_dependency[name] = DependencyInfo();
      persona_steps[name] = base_step();
      // available_agents.push_back(name);
      ready_agents.push_back(name);
    }
  }

  void add_persona_dependency(const std::string &persona_name,
                              const std::string &blocking) {
    persona_dependency.at(persona_name).blocking.insert(blocking);
    persona_dependency.at(blocking).blocked.insert(persona_name);
  }

  void remove_persona_dependency(const std::string &persona_name,
                                 const std::string &blocking) {
    persona_dependency.at(persona_name).blocking.erase(blocking);
    persona_dependency.at(blocking).blocked.erase(persona_name);
  }

  bool can_proceed(const std::string &persona_name) {
    return persona_dependency.at(persona_name).blocked.empty();
  }

  bool can_proceed_dist(const std::string &persona_name) {
    return redis_client_pool.smembers("persona:" + persona_name + ":blocked")
        .empty();
  }

  std::tuple<int, int> get_persona_position(const std::string &persona_name) {
    int x = std::stoi(redis_client_pool.hget("persona:" + persona_name, "x"));
    int y = std::stoi(redis_client_pool.hget("persona:" + persona_name, "y"));
    return std::make_tuple(x, y);
  }

  std::vector<std::pair<std::string, double>> geo_query_personas(
      const std::string &persona_name, int vision_radius = -1,
      bool closed_interval = true) {
    if (vision_radius == -1) {
      vision_radius = agent_vision_radius;
    }

    auto position = get_persona_position(persona_name);
    int center_x = std::get<0>(position);
    int center_y = std::get<1>(position);

    std::vector<std::string> keys;
    for (int x = center_x - vision_radius; x <= center_x + vision_radius; ++x) {
      for (int y = center_y - vision_radius; y <= center_y + vision_radius;
           ++y) {
        keys.push_back("grid:" + std::to_string(x) + ":" + std::to_string(y));
      }
    }

    std::vector<std::string> results =
        redis_client_pool.pipeline_hget(keys, "personas");

    std::vector<std::pair<std::string, double>> personas;
    for (size_t i = 0; i < keys.size(); ++i) {
      const auto &result = results[i];
      if (!result.empty() && result != persona_name) {
        auto key_parts = split(keys[i], ':');
        int x = std::stoi(key_parts[1]);
        int y = std::stoi(key_parts[2]);
        double dist =
            std::sqrt(std::pow(x - center_x, 2) + std::pow(y - center_y, 2));
        if (dist < vision_radius ||
            (closed_interval && dist == vision_radius)) {
          for (auto p : split(result, ':')) {
            if (p != persona_name) {
              personas.emplace_back(p, dist);
            }
          }
        }
      }
    }

    return personas;
  }

  std::vector<std::pair<std::string, double>> geo_distances(
      const std::string &persona_name,
      const std::unordered_set<std::string> &personas) {
    auto position = get_persona_position(persona_name);
    int center_x = std::get<0>(position);
    int center_y = std::get<1>(position);

    std::vector<std::pair<std::string, double>> distances;
    for (const auto &p : personas) {
      auto pos = get_persona_position(p);
      int x = std::get<0>(pos);
      int y = std::get<1>(pos);
      double dist =
          std::sqrt(std::pow(x - center_x, 2) + std::pow(y - center_y, 2));
      distances.emplace_back(p, dist);
    }

    return distances;
  }

  int base_step() {
    return std::stoi(redis_client_pool.get("counter:base_step"));
  }
  int max_step() {
    return std::stoi(redis_client_pool.get("counter:max_step"));
  }

  void update_agent_status_sync(const std::vector<std::string> &updated_agents,
                                int persona_step, bool completed = false) {
    for (auto agent : updated_agents) {
      persona_steps[agent] = persona_step;
      if (completed) {
        completed_agents.push_back(agent);
        if (INSTRUMENTATION_ENABLED) {
          redis_client_updating.hset("persona:" + agent, "status", "completed");
        }
      } else {
        available_agents.push_back(agent);
        if (INSTRUMENTATION_ENABLED) {
          redis_client_updating.hset("persona:" + agent, "status", "available");
        }
      }
    }
    if (available_agents.size() + completed_agents.size() ==
        persona_steps.size()) {
      for (const auto &agent : available_agents) {
        ready_agents.push_back(agent);
        if (INSTRUMENTATION_ENABLED) {
          redis_client_updating.hset("persona:" + agent, "status", "ready");
        }
      }
      available_agents.clear();
    }
  }

  void update_agent_status_oracle(
      const std::vector<std::string> &updated_agents, int persona_step,
      bool completed = false) {
    for (auto agent : updated_agents) {
      persona_steps[agent] = persona_step;

      auto blocking =
          redis_client_updating.smembers("oracle_dependency:" + agent + ":" +
                                         std::to_string(persona_step - 1));
      for (const auto &b : blocking) {
        auto update_key = "oracle_dependency_current:" + b;
        while (true) {
          try {
            redis_client_updating.watch(update_key);
            redis_client_updating.multi();
            redis_client_updating.srem(
                update_key, agent + ":" + std::to_string(persona_step - 1));
            redis_client_updating.exec();
            break;
          } catch (const std::runtime_error &e) {
            continue;
          }
        }
      }

      if (completed) {
        completed_agents.push_back(agent);
        if (INSTRUMENTATION_ENABLED) {
          redis_client_updating.hset("persona:" + agent, "status", "completed");
        }
      } else {
        available_agents.push_back(agent);
        if (INSTRUMENTATION_ENABLED) {
          redis_client_updating.hset("persona:" + agent, "status", "available");
        }
      }
    }

    auto readys =
        redis_client_updating.pipeline_oracle_dep_check(available_agents);
    std::vector<size_t> to_move_index;
    for (size_t i = 0; i < readys.size(); ++i) {
      if (readys[i]) {
        std::lock_guard<std::mutex> lock(update_mutex);
        ready_agents.push_back(available_agents[i]);
        to_move_index.push_back(i);
      }
    }

    for (auto i = to_move_index.rbegin(); i != to_move_index.rend(); ++i) {
      available_agents.erase(available_agents.begin() + *i);
    }
  }

  // todo: partition the agents for parallelizing the geo clustering
  void prepare_ready_clusters(const std::vector<std::string> &updated_agents,
                              int persona_step) {
    for (auto agent : updated_agents) {
      persona_steps[agent] = persona_step;
      available_agents.push_back(agent);
      if (INSTRUMENTATION_ENABLED) {
        redis_client_updating.hset("persona:" + agent, "status", "available");
      }
    }
  }

  void update_agent_status(
      const std::vector<std::pair<int, std::vector<std::string>>>
          &updated_clusters,
      int target_step) {
    record_timestamp_dep(Instrumentation::DepStart);
    // if (persona_step > max_step()) {
    //   redis_client_updating.set_int("counter:max_step", persona_step);
    // }
    for (const auto &cluster : updated_clusters) {
      const auto &persona_step = cluster.first;
      const auto &updated_agents = cluster.second;
      for (const auto &agent : updated_agents) {
        persona_steps[agent] = persona_step;
        if (persona_step == target_step) {
          completed_agents.push_back(agent);
          // todo, put it in a debug macro
          if (INSTRUMENTATION_ENABLED) {
            redis_client_updating.hset("persona:" + agent, "status",
                                       "completed");
          }
        } else {
          available_agents.push_back(agent);
          if (INSTRUMENTATION_ENABLED) {
            redis_client_updating.hset("persona:" + agent, "status",
                                       "available");
          }
        }
      }
    }

    record_timestamp_dep(Instrumentation::DepLoopStart);
    auto readys = redis_client_updating.pipeline_dep_check(available_agents);

    record_timestamp_dep(Instrumentation::DepUpdatingAgentStatus);
    std::vector<size_t> to_move_index;
    for (size_t i = 0; i < readys.size(); ++i) {
      if (readys[i]) {
        std::lock_guard<std::mutex> lock(update_mutex);
        ready_agents.push_back(available_agents[i]);
        to_move_index.push_back(i);
      }
    }

    for (auto i = to_move_index.rbegin(); i != to_move_index.rend(); ++i) {
      if (INSTRUMENTATION_ENABLED) {
        redis_client_updating.hset("persona:" + available_agents[*i], "status",
                                   "ready");
      }
      available_agents.erase(available_agents.begin() + *i);
    }
    record_timestamp_dep(Instrumentation::DepEnd);
  }

  void update_dependency_dist(const std::vector<std::string> &updated_agents,
                              int persona_step) {
    auto process_agent = [&](const auto &agent) {
      // record_timestamp_dep(Instrumentation::DepGeoQuery);
      auto coupled_agents = geo_query_personas(
          agent, agent_vision_radius + persona_step - base_step() + 1);
      auto blocking_persona_dists = geo_distances(
          agent,
          redis_client_updating.smembers("persona:" + agent + ":blocking"));
      for (auto b : blocking_persona_dists) {
        // redis_client_updating.watch("persona:" + b.first);
        coupled_agents.push_back(b);
      }

      std::unordered_set<std::string> new_blocking;
      std::unordered_set<std::string> new_blocked;

      // record_timestamp_dep(Instrumentation::DepCalculating);
      for (auto pair = coupled_agents.begin(); pair != coupled_agents.end();
           ++pair) {
        const auto &p = pair->first;
        const auto &dist = pair->second;

        int coupled_step =
            std::stoi(redis_client_updating.hget("persona:" + p, "step"));
        if (dist <= agent_vision_radius) {
          CORRECTNESS_CHECK(
              persona_step == coupled_step,
              agent + " (" + std::to_string(persona_step) + ") and " + p +
                  " (" + std::to_string(coupled_step) + ") with distance " +
                  std::to_string(dist) + " are not in the same step.");
        } else if (dist <= std::abs(persona_step - coupled_step) +
                               agent_vision_radius + 1) {
          if (persona_step != coupled_step) {
            CORRECTNESS_CHECK(dist > agent_vision_radius +
                                         std::abs(persona_step - coupled_step) -
                                         1,
                              "conflict detected between " + agent + " (" +
                                  std::to_string(persona_step) + ") and " + p +
                                  " (" + std::to_string(coupled_step) +
                                  ") with distance " + std::to_string(dist));
            if (persona_step < coupled_step) {
              new_blocking.insert(p);
            } else {
              new_blocked.insert(p);
            }
          }
        }
        // If the two agents are far away, do nothing
      }
      return std::make_tuple(new_blocking, new_blocked, agent);
    };

    for (const auto &agent : updated_agents) {
      std::unordered_set<std::string> new_blocking;
      std::unordered_set<std::string> new_blocked;
      while (true) {
        try {
          std::string blocking_key = "persona:" + agent + ":blocking";
          std::string blocked_key = "persona:" + agent + ":blocked";
          redis_client_updating.watch(blocking_key);
          // redis_client_updating.watch(blocked_key);

          auto result = process_agent(agent);
          new_blocking = std::get<0>(result);
          new_blocked = std::get<1>(result);

          // the current_blocking actually does not cover the new_blocking
          auto current_blocking = redis_client_updating.smembers(blocking_key);
          for (const auto &a : set_difference(current_blocking, new_blocking)) {
            // redis_client_updating.watch("persona:" + a);
            redis_client_updating.watch("persona:" + a + ":blocked");
          }

          auto current_blocked = redis_client_updating.smembers(blocked_key);
          CORRECTNESS_CHECK(current_blocked.empty(),
                            "Current blocked set is not empty for " + agent);
          for (const auto &a : set_difference(new_blocked, current_blocked)) {
            // redis_client_updating.watch("persona:" + a);
            redis_client_updating.watch("persona:" + a + ":blocking");
          }

          redis_client_updating.multi();
          for (const auto &a : set_difference(current_blocking, new_blocking)) {
            redis_client_updating.remove_dependency(agent, a);
          }
          for (const auto &a : set_difference(new_blocked, current_blocked)) {
            redis_client_updating.add_dependency(a, agent);
          }
          redis_client_updating.exec();
          break;
        } catch (const std::runtime_error &e) {
          // std::cerr << e.what() << std::endl;
          // std::cout << "Retrying transaction" << std::endl;
          continue;  // Retry the transaction
        }
      }
    }
  }

  // todo, clean up deprarated functions
  void update_dependency(const std::vector<std::string> &updated_agents,
                         int persona_step, bool completed = false) {
    record_timestamp_dep(Instrumentation::DepStart);

    // since there won't be dependency between agents in the same step, we can
    // update the dependency in parallel
    auto process_agent = [&](const auto &agent) {
      persona_steps[agent] = persona_step;

      // record_timestamp_dep(Instrumentation::DepGeoQuery);
      auto coupled_agents = geo_query_personas(
          agent, agent_vision_radius + persona_step - base_step() + 1);

      auto blocking_persona_dists =
          geo_distances(agent, persona_dependency.at(agent).blocking);
      for (auto b : blocking_persona_dists) {
        coupled_agents.push_back(b);
      }

      std::unordered_set<std::string> new_blocking;
      std::unordered_set<std::string> new_blocked;

      // record_timestamp_dep(Instrumentation::DepCalculating);
      for (auto pair = coupled_agents.begin(); pair != coupled_agents.end();
           ++pair) {
        const auto &p = pair->first;
        const auto &dist = pair->second;

        int coupled_step =
            std::stoi(redis_client_pool.hget("persona:" + p, "step"));
        if (dist <= agent_vision_radius) {
          if (persona_step != coupled_step) {
            throw std::runtime_error(
                agent + " (" + std::to_string(persona_step) + ") and " + p +
                " (" + std::to_string(coupled_step) + ") with distance " +
                std::to_string(dist) + " are not in the same step.");
          }
        } else if (dist <= std::abs(persona_step - coupled_step) +
                               agent_vision_radius + 1) {
          if (persona_step != coupled_step) {
            if (dist <= agent_vision_radius +
                            std::abs(persona_step - coupled_step) - 1) {
              throw std::runtime_error(
                  "conflict detected between " + agent + " (" +
                  std::to_string(persona_step) + ") and " + p + " (" +
                  std::to_string(coupled_step) + ") with distance " +
                  std::to_string(dist));
            }
            if (persona_step < coupled_step) {
              new_blocking.insert(p);
            } else {
              new_blocked.insert(p);
            }
          }
        }
        // If the two agents are far away, do nothing
      }
      return std::make_tuple(new_blocking, new_blocked, agent);
    };

    // Vector to hold future objects
    std::vector<
        std::future<std::tuple<std::unordered_set<std::string>,
                               std::unordered_set<std::string>, std::string>>>
        futures;

    // Launch tasks in parallel
    for (const auto &agent : updated_agents) {
      futures.push_back(std::async(std::launch::async, process_agent, agent));
    }

    record_timestamp_dep(Instrumentation::DepLoopStart);
    // Wait for all tasks to complete
    for (auto &fut : futures) {
      auto result = fut.get();
      // for (const auto &agent : updated_agents) {
      // auto result = process_agent(agent);
      record_timestamp_dep(Instrumentation::DepUpdatingDep);
      auto new_blocking = std::get<0>(result);
      auto new_blocked = std::get<1>(result);
      auto agent = std::get<2>(result);

      auto &current_blocking = persona_dependency.at(agent).blocking;
      auto &current_blocked = persona_dependency.at(agent).blocked;

      for (const auto &a : set_difference(current_blocking, new_blocking)) {
        remove_persona_dependency(agent, a);
      }
      for (const auto &a : set_difference(new_blocked, current_blocked)) {
        add_persona_dependency(a, agent);
      }

      record_timestamp_dep(Instrumentation::DepUpdatingAgentStatus);
      if (completed) {
        completed_agents.push_back(agent);
        redis_client_pool.hset("persona:" + agent, "status", "completed");
      } else {
        std::lock_guard<std::mutex> lock(update_mutex);
        available_agents.push_back(agent);
        redis_client_pool.hset("persona:" + agent, "status", "available");
      }
    }
    record_timestamp_dep(Instrumentation::DepEnd);
  }

  // if this is faster enough, we should update the base step more frequently
  int update_base_step() {
    auto min_step = std::min_element(persona_steps.begin(), persona_steps.end(),
                                     [](const auto &lhs, const auto &rhs) {
                                       return lhs.second < rhs.second;
                                     });
    int diff = min_step->second - base_step();
    if (diff > 0) {
      redis_client_pool.set_int("counter:base_step", min_step->second);
    }
    return diff;
  }

  void geo_clustering_relaxed(py::object task_queue) {
    std::vector<std::string> local_ready_agents(ready_agents);
    std::vector<std::string> clustered_agents;

    // all available agents are free to go without clustering
    for (const auto &agent : local_ready_agents) {
      int cluster_step =
          std::stoi(redis_client_clustering.hget("persona:" + agent, "step"));
      std::vector<std::string> cluster = {agent};
      py::gil_scoped_acquire acquire;
      task_queue.attr("put")(std::make_tuple(cluster_step, cluster));
      py::gil_scoped_release release;
      clustered_agents.push_back(agent);
      continue;
    }

    std::lock_guard<std::mutex> lock(update_mutex);
    for (const auto &agent : clustered_agents) {
      ready_agents.erase(
          std::find(ready_agents.begin(), ready_agents.end(), agent));
    }
  }

  // todo, make it a macro or template
  void record_timestamp(const Instrumentation label) {
    if (INSTRUMENTATION_ENABLED) {
      timestamps.push_back(
          std::make_pair(std::chrono::high_resolution_clock::now(), label));
    }
  }

  void record_timestamp_dep(const Instrumentation label) {
    if (INSTRUMENTATION_ENABLED) {
      dep_timestamps.push_back(
          std::make_pair(std::chrono::high_resolution_clock::now(), label));
    }
  }

  void geo_clustering(py::object task_queue, bool speculation) {
    record_timestamp(Instrumentation::Start);
    std::unordered_set<std::string> visited;
    std::vector<std::tuple<int, std::vector<std::string>>> clusters;

    int coupling_radius = agent_vision_radius;
    if (speculation) {
      coupling_radius = agent_vision_radius + 1;
    }

    std::vector<std::string> local_ready_agents(ready_agents);
    std::vector<std::string> clustered_agents;

    for (const auto &agent : local_ready_agents) {
      record_timestamp(Instrumentation::LoopStart);

      if (visited.find(agent) != visited.end()) {
        continue;
      }

      CORRECTNESS_CHECK(can_proceed_dist(agent),
                        "Agent " + agent + " in ready list cannot proceed");

      std::vector<std::string> cluster;
      std::vector<std::string> queue = {agent};
      bool cluster_proceed_indicator = true;
      int cluster_step =
          std::stoi(redis_client_clustering.hget("persona:" + agent, "step"));

      while (!queue.empty()) {
        if (cluster_proceed_indicator == false) {
          // if the cluster is blocked already,
          // clear the queue to reduce redundant I/O
          for (const auto &a : queue) {
            visited.insert(a);
          }
          queue.clear();
          break;
        }

        std::string current = queue.front();
        queue.erase(queue.begin());

        if (visited.find(current) != visited.end()) {
          if (std::find(cluster.begin(), cluster.end(), current) ==
              cluster.end()) {
            // coupled agent is already blocked
            cluster_proceed_indicator = false;
          }
          continue;
        }

        visited.insert(current);
        cluster.push_back(current);

        record_timestamp(Instrumentation::GeoQuery);
        // todo: a potential bottleneck, to be fully parallelized
        auto coupled_agents = geo_query_personas(current, coupling_radius);
        record_timestamp(Instrumentation::AvailabilityCheck);

        for (auto pair = coupled_agents.begin(); pair != coupled_agents.end();
             ++pair) {
          const auto &persona = pair->first;
          const auto &dist = pair->second;
          int persona_step = std::stoi(
              redis_client_clustering.hget("persona:" + persona, "step"));

          bool persona_ready =
              std::find(local_ready_agents.begin(), local_ready_agents.end(),
                        persona) != local_ready_agents.end();

          if (!persona_ready) {
            if (dist > agent_vision_radius && persona_step > cluster_step) {
              // the only exception is that the agent is in the next step hence
              // it is not coupled with the cluster nor blocking the cluster
            } else {
              // otherwise, one not ready agent will block the whole cluster
              cluster_proceed_indicator = false;
              continue;
            }
          } else {
            // todo, assertion check
            queue.push_back(persona);
          }
        }
      }

      if (speculation && !cluster_proceed_indicator) {
        continue;
      }

      record_timestamp(Instrumentation::UpdatingTaskQueue);
      // Push to Python multiprocessing queue
      py::gil_scoped_acquire acquire;
      task_queue.attr("put")(std::make_tuple(cluster_step, cluster));
      py::gil_scoped_release release;

      for (const auto &agent : cluster) {
        clustered_agents.push_back(agent);
      }
    }

    record_timestamp(Instrumentation::UpdatingAgentStatus);
    if (INSTRUMENTATION_ENABLED) {
      redis_client_clustering.pipeline_hset(clustered_agents, "status",
                                            "processing");
    }
    std::lock_guard<std::mutex> lock(update_mutex);
    for (const auto &agent : clustered_agents) {
      ready_agents.erase(
          std::find(ready_agents.begin(), ready_agents.end(), agent));
    }

    record_timestamp(Instrumentation::End);
  }

  void dump_trace(const std::string &filename) const {
    std::ofstream file(filename);
    if (file.is_open()) {
      file << "Start,End,Duration (microseconds)\n";
      for (size_t i = 1; i < timestamps.size(); ++i) {
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(
                            timestamps[i].first - timestamps[i - 1].first)
                            .count();
        file << instrumentation_to_string(timestamps[i - 1].second) << ","
             << instrumentation_to_string(timestamps[i].second) << ","
             << duration << "\n";
      }
      for (size_t i = 1; i < dep_timestamps.size(); ++i) {
        auto duration =
            std::chrono::duration_cast<std::chrono::microseconds>(
                dep_timestamps[i].first - dep_timestamps[i - 1].first)
                .count();
        file << instrumentation_to_string(dep_timestamps[i - 1].second) << ","
             << instrumentation_to_string(dep_timestamps[i].second) << ","
             << duration << "\n";
      }

      file.close();
    } else {
      std::cerr << "Unable to open file for writing: " << filename << std::endl;
    }
  }

  int num_available_agents() {
    return available_agents.size() + ready_agents.size();
  }
  int num_completed_agents() { return completed_agents.size(); }

 private:
  std::unordered_map<std::string, DependencyInfo> persona_dependency;
  std::unordered_map<std::string, int> persona_steps;
  std::vector<std::string> available_agents;
  std::vector<std::string> completed_agents;
  std::vector<std::string> ready_agents;
  std::vector<std::vector<std::string>> ready_clusters;
  std::mutex update_mutex;
  int agent_vision_radius;
  // default redis client
  RedisClient redis_client_updating;
  RedisClient redis_client_clustering;
  // extra client pool for parallel processing
  // todo: we might not need a client pool for a lot of cases now
  RedisClientPool redis_client_pool;
  std::vector<std::pair<std::chrono::high_resolution_clock::time_point,
                        Instrumentation>>
      timestamps;
  std::vector<std::pair<std::chrono::high_resolution_clock::time_point,
                        Instrumentation>>
      dep_timestamps;
};

PYBIND11_MODULE(aimetropoliscpp, m) {
  py::class_<PersonaDependency>(m, "PersonaDependency")
      .def(py::init<const std::vector<std::string> &, int, const std::string &,
                    int, int>())
      .def("can_proceed", &PersonaDependency::can_proceed)
      // .def("update", &PersonaDependency::update_dependency)
      .def("geo_clustering", &PersonaDependency::geo_clustering)
      .def("geo_clustering_relaxed", &PersonaDependency::geo_clustering_relaxed)
      .def("update_base_step", &PersonaDependency::update_base_step)
      .def("num_available_agents", &PersonaDependency::num_available_agents)
      .def("num_completed_agents", &PersonaDependency::num_completed_agents)
      .def("update_agent_status", &PersonaDependency::update_agent_status)
      .def("dump_trace", &PersonaDependency::dump_trace)
      .def("update_agent_status_sync",
           &PersonaDependency::update_agent_status_sync)
      .def("update_agent_status_oracle",
           &PersonaDependency::update_agent_status_oracle)
      .def("update_dist", &PersonaDependency::update_dependency_dist);
}
