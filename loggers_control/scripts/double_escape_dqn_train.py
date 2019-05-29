#! /usr/bin/env python
"""
Training two logger robots escaping a cell with Deep Q-network (DQN)
DQN is a model free, off policy, reinforcement learning algorithm (https://deepmind.com/research/dqn/)
Author: LinZHanK (linzhank@gmail.com)
"""
from __future__ import absolute_import, division, print_function

import sys
import os
from datetime import datetime
import numpy as np
import tensorflow as tf
import rospy

from envs.double_escape_task_env import DoubleEscapeEnv
from utils import gen_utils, double_utils, tf_utils
from utils.gen_utils import bcolors
from agents.dqn import DQNAgent

import pdb


if __name__ == "__main__":
    # start_time = time.time()
    rospy.init_node("double_escape_dqn", anonymous=True, log_level=rospy.INFO)
    # make an instance from env class
    env = DoubleEscapeEnv()
    env.reset()
    agent0_params = {}
    agent1_params = {}
    train_params = {}
    # agent_0 parameters
    agent0_params["dim_state"] = len(double_utils.obs_to_state(env.observation, "all"))
    agent0_params["actions"] = np.array([np.array([1, -1]), np.array([1, 1])])
    agent0_params["layer_size"] = [256,256]
    agent0_params["gamma"] = 0.99
    agent0_params["learning_rate"] = 3e-4
    agent0_params["batch_size"] = 2000
    agent0_params["memory_cap"] = 500000
    agent0_params["update_step"] = 10000
    agent0_params["model_path"] = os.path.dirname(sys.path[0])+"/saved_models/double_escape/dqn_model/"+datetime.now().strftime("%Y-%m-%d-%H-%M")+"/agent0/model.h5"
    # agent_1 parameters
    agent1_params["dim_state"] = len(double_utils.obs_to_state(env.observation, "all"))
    agent1_params["actions"] = agent0_params["actions"]
    agent1_params["layer_size"] = [256,256]
    agent1_params["epsilon"] = 1
    agent1_params["gamma"] = 0.99
    agent1_params["learning_rate"] = 1e-3
    agent1_params["batch_size"] = 2000
    agent1_params["memory_cap"] = 500000
    agent1_params["update_step"] = 10000
    agent1_params["model_path"] = os.path.dirname(sys.path[0])+"/saved_models/double_escape/dqn_model/"+datetime.now().strftime("%Y-%m-%d-%H-%M")+"/agent1/model.h5"
    # training parameters
    train_params["num_episodes"] = 6000
    train_params["num_steps"] = 400
    train_params["time_bonus"] = -1./train_params["num_steps"]
    train_params["success_bonus"] = 10
    train_params["wall_bonus"] = -10./train_params["num_steps"]
    train_params["door_bonus"] = 0
    # instantiate agents
    agent_0 = DQNAgent(agent0_params)
    agent_1 = DQNAgent(agent1_params)
    update_counter = 0
    ep_returns = []
    for ep in range(train_params["num_episodes"]):
        epsilon_0 = agent_0.epsilon_decay(ep, train_params["num_episodes"])
        epsilon_1 = agent_1.epsilon_decay(ep, train_params["num_episodes"])
        print("epsilon_0: {}, epsilon_1: {}".format(epsilon_0, epsilon_1))
        obs, _ = env.reset()
        state_agt0 = double_utils.obs_to_state(obs, "all")
        state_agt1 = double_utils.obs_to_state(obs, "all") # state of agent0 and agent1 could be same if using "all" option, when converting obs
        done, ep_rewards = False, []
        for st in range(train_params["num_steps"]):
            agent0_acti = agent_0.epsilon_greedy(state_agt0)
            agent0_action = agent_0.actions[agent0_acti]
            agent1_acti = agent_1.epsilon_greedy(state_agt1)
            agent1_action = agent_1.actions[agent1_acti]
            obs, rew, done, info = env.step(agent0_action, agent1_action)
            next_state_agt0 = double_utils.obs_to_state(obs, "all")
            next_state_agt1 = double_utils.obs_to_state(obs, "all")
            # adjust reward based on bonus options
            rew, done = double_utils.adjust_reward(train_params, env)
            ep_rewards.append(rew)
            # rew, done = double_utils.adjust_reward(hyp_params, env, agent)
            print(
                bcolors.OKGREEN,
                "Episode: {}, Step: {}: \naction0: {}->{}, action0: {}->{}, agent_0 state: {}, agent_1 state: {}, reward/episodic_return: {}/{}, status: {}, succeeds: {}".format(
                    ep,
                    st,
                    agent0_acti,
                    agent0_action,
                    agent1_acti,
                    agent1_action,
                    next_state_agt0,
                    next_state_agt1,
                    rew,
                    sum(ep_rewards),
                    info,
                    env.success_count
                ),
                bcolors.ENDC
            )
            # store transition
            agent_0.replay_memory.store((state_agt0, agent0_acti, rew, done, next_state_agt0))
            agent_1.replay_memory.store((state_agt1, agent1_acti, rew, done, next_state_agt1))
            agent_0.train()
            agent_1.train()
            state_agt0 = next_state_agt0
            state_agt1 = next_state_agt1
            update_counter += 1
            if not update_counter % agent_0.update_step:
                agent_0.qnet_stable.set_weights(agent_0.qnet_active.get_weights())
                print(bcolors.BOLD, "agent_0 Q-net weights updated!", bcolors.ENDC)
            if not update_counter % agent_1.update_step:
                agent_1.qnet_stable.set_weights(agent_1.qnet_active.get_weights())
                print(bcolors.BOLD, "agent_1 Q-net weights updated!", bcolors.ENDC)
            if done:
                break
        ep_returns.append(sum(ep_rewards))
        agent_0.save_model()
        agent_1.save_model()

    # end of training
    env.reset()
    # plot deposit returns
    gen_utils.plot_returns(returns=ep_returns, mode=2, save_flag=True, path=os.path.dirname(agent0_params["model_path"]))
    # save results
    gen_utils.save_pkl(content=agent0_params, path=agent0_params["model_path"], fname="agent0_parameters.pkl")
    gen_utils.save_pkl(content=agent1_params, path=agent1_params["model_path"], fname="agent1_parameters.pkl")
    # save results
    train_info = train_params
    train_info["success_count"] = env.success_count
    train_info["agent_0"] = agent0_params
    train_info["agent_1"] = agent1_params
    gen_utils.save_csv(content=train_info, path=os.path.dirname(agent0_params["model_path"]), fname="train_information.csv")
