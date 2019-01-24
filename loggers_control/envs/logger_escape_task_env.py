from __future__ import print_function

import rospy
import numpy as np
import time
import math
import random
import tf
from gym import spaces
from .loggers_robot_env import LoggersRobotEnv
from gym.envs.registration import register

from gazebo_msgs.msg import ModelState
from geometry_msgs.msg import Pose, Twist

# Register crib env 
register(
  id='SoloEscape-v0',
  entry_point='envs.logger_escape_task_env:SoloEscapeTaskEnv')


class SoloEscapeTaskEnv(LoggersRobotEnv):
  def __init__(self):
    """
    This task-env is designed for a mobile robot(Logger) escape a walled cell 
    through the only exit. Action and state space will be both set to continuous. 
    """
    # action limits
    self.max_linear_speed = .8
    self.max_angular_speed = math.pi / 3
    # observation limits
    self.max_x = 5
    self.max_y = 5
    self.max_vx = 2
    self.max_vy = 2
    self.max_cosyaw = 1
    self.max_sinyaw = 1
    self.max_yawdot = math.pi
    # action space
    self.high_action = np.array([self.max_linear_speed, self.max_angular_speed])
    self.low_action = -self.high_action
    self.action_space = spaces.Box(low=self.low_action, high=self.high_action)
    # observation space
    self.high_observation = np.array(
      [
        self.max_x,
        self.max_y,
        self.max_vx,
        self.max_vy,
        self.max_cosyaw,
        self.max_sinyaw,
        self.max_yawdot
      ]
    )
    self.low_observation = -self.high_observation
    self.observation_space = spaces.Box(low=self.low_observation, high=self.high_observation) 
    # observation
    self.observation = np.zeros(self.observation_space.shape[0])
    self.observation[4] = self.max_cosyaw
    # info, initial position and goal position
    self.init_position = np.zeros(2)
    self.current_position = np.zeros(2)
    self.previous_position = np.zeros(2)
    self.goal_position = np.zeros(2)
    self.info = {}
    # Set model state
    self.set_robot_state_publisher = rospy.Publisher("/gazebo/set_model_state", ModelState, queue_size=100)
    # self.set_model_state = rospy.ServiceProxy('/gazebo/set_model_state', SetModelState)
    self._episode_done = False
    # Here we will add any init functions prior to starting the MyRobotEnv
    super(SoloEscapeTaskEnv, self).__init__()

  def _set_init(self):
    """ 
    Set initial condition for simulation
      Set Logger at a random pose inside cell by publishing /gazebo/set_model_state topic
    Returns: 
      init_position: array([x, y]) 
    """
    rospy.logdebug("Start initializing robot...")
    self.current_position = self.init_position
    # set turtlebot inside crib, away from crib edges
    mag = random.uniform(0, 4) # robot vector magnitude
    ang = random.uniform(-math.pi, math.pi) # robot vector orientation
    x = mag * math.cos(ang)
    y = mag * math.sin(ang)
    w = random.uniform(-1.0, 1.0)    
    robot_state = ModelState()
    robot_state.model_name = "logger"
    robot_state.pose.position.x = x
    robot_state.pose.position.y = y
    robot_state.pose.position.z = 0
    robot_state.pose.orientation.x = 0
    robot_state.pose.orientation.y = 0
    robot_state.pose.orientation.z = math.sqrt(1 - w**2)
    robot_state.pose.orientation.w = w
    robot_state.reference_frame = "world"  
    self.init_position = np.array([x, y])

    # set goal point using pole coordinate
    for _ in range(10):
      self.set_robot_state_publisher.publish(robot_state)
      rate.sleep()
    
    rospy.logwarn("Robot was initiated as {}".format(self.init_position))
    # Episode cannot done
    self._episode_done = False
    # Give the system a little time to finish initialization
    rospy.logdebug("Finished initialize robot.")
    
    return self.init_position
    
  def _take_action(self, action):
    """
    Drive the Logger with differential driving controller.
    Args:
      action: numpy array([linear_speed, angular_speed])
    """
    cmd_vel = Twist()
    cmd_vel.linear.x = action[0]
    cmd_vel.angular.z = action[1]
    self._check_publishers_connection()
    rate = rospy.Rate(100)
    # publish /cmd_vel for 0.1s at 100 Hz
    for _ in range(10):
      self._cmd_vel_pub.publish(cmd_vel) # refer to loggers_robot_env
      rospy.logdebug("cmd_vel: {}".format(cmd_vel))
      rate.sleep()

  def _get_observation(self):
    """
    Get observations from env
    Return:
      observation: [x, y, v_x, v_y, cos(yaw), sin(yaw), yaw_dot]
    """
    rospy.logdebug("Start Getting Observation ==>")
    self.previous_position = self.current_position    
    model_states = self.get_model_states() # refer to loggers_robot_env
    # update previous position
    rospy.logdebug("model_states: {}".format(model_states))
    x = model_states.pose[-1].position.x # logger was the last model in model_states
    y = model_states.pose[-1].position.y
    self.current_position = np.array([x, y])
    v_x = model_states.twist[-1].linear.x
    v_y = model_states.twist[-1].linear.y
    quat = (
      model_states.pose[-1].orientation.x,
      model_states.pose[-1].orientation.y,
      model_states.pose[-1].orientation.z,
      model_states.pose[-1].orientation.w
    )
    euler = tf.transformations.euler_from_quaternion(quat)
    cos_yaw = math.cos(euler[2])
    sin_yaw = math.sin(euler[2])
    yaw_dot = model_states.twist[-1].angular.z
    
    self.observation = np.array([x, y, v_x, v_y, cos_yaw, sin_yaw, yaw_dot])
    rospy.logdebug("Observation ==> {}".format(self.observation))
    
    return self.observation

  def _post_information(self):
    """
    Return:
      info: {"init_position", "goal_position", "current_position", "previous_position"}
    """
    self.info = {
      "init_position": self.init_position,
      "current_position": self.current_position,
      "previous_position": self.previous_position,
    }
    
    return self.info

  def _is_done(self):
    """
    Return done if self._episode_done == True
    """
    return self._episode_done

  def _compute_reward(self):
    if sum(np.absolute(self.current_position)>4.6): # turtlebot close to edge
      reward = 0
      self._episode_done = True
      rospy.logwarn("Logger is too close to the edge, task will be reset!")
    elif self.current_position[1] <= 6: # turtle bot close to goal
      reward = 0
      self._episode_done = False
      rospy.logwarn("Logger is working on its way to escape...")
    else:
      reward = 1
      self._episode_done = True
      rospy.logwarn("\n!!!\nLogger Escaped !\n!!!")
    rospy.logdebug("Reward in current step = {}".format(reward))
    
    return reward


def _check_publishers_connection(self):
  raise NotImplementedError()

def _cmd_vel_pub(self):
  raise NotImplementedError()
