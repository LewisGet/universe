import logging

import gym
from universe import error, spaces
from universe import vectorized

logger = logging.getLogger(__name__)


def atari_vnc(up=False, down=False, left=False, right=False, z=False):
    return [spaces.KeyEvent.by_name('up', down=up),
            spaces.KeyEvent.by_name('left', down=left),
            spaces.KeyEvent.by_name('right', down=right),
            spaces.KeyEvent.by_name('down', down=down),
            spaces.KeyEvent.by_name('z', down=z)]

def slither_vnc(space=False, left=False, right=False):
    return [spaces.KeyEvent.by_name('space', down=space),
            spaces.KeyEvent.by_name('left', down=left),
            spaces.KeyEvent.by_name('right', down=right)]

def racing_vnc(up=False, left=False, right=False):
    return [spaces.KeyEvent.by_name('up', down=up),
            spaces.KeyEvent.by_name('left', down=left),
            spaces.KeyEvent.by_name('right', down=right)]

def platform_vnc(up=False, left=False, right=False, space=False):
    return [spaces.KeyEvent.by_name('up', down=up),
            spaces.KeyEvent.by_name('left', down=left),
            spaces.KeyEvent.by_name('right', down=right),
            spaces.KeyEvent.by_name('space', down=space)]

def gym_core_action_space(gym_core_id):
    spec = gym.spec(gym_core_id)

    if spec.id == 'CartPole-v0':
        return spaces.Hardcoded([[spaces.KeyEvent.by_name('left', down=True)],
                                 [spaces.KeyEvent.by_name('left', down=False)]])
    elif spec._entry_point.startswith('gym.envs.atari:'):
        actions = []
        env = spec.make()
        for action in env.unwrapped.get_action_meanings():
            z = 'FIRE' in action
            left = 'LEFT' in action
            right = 'RIGHT' in action
            up = 'UP' in action
            down = 'DOWN' in action
            translated = atari_vnc(up=up, down=down, left=left, right=right, z=z)
            actions.append(translated)
        return spaces.Hardcoded(actions)
    else:
        raise error.Error('Unsupported env type: {}'.format(spec.id))


class SoftmaxClickMouse(vectorized.ActionWrapper):
    def __init__(self, env, active_region=(10, 75 + 50, 10 + 160, 75 + 210), discrete_mouse_step=10, noclick_regions=[]):
        super(SoftmaxClickMouse, self).__init__(env)
        xlow, ylow, xhigh, yhigh = active_region
        xs = range(xlow, xhigh, discrete_mouse_step)
        ys = range(ylow, yhigh, discrete_mouse_step)
        self._actions = []
        removed = 0
        for x in xs:
            for y in ys:
                xc = min(x+int(discrete_mouse_step/2), xhigh-1) # click to center of a cell
                yc = min(y+int(discrete_mouse_step/2), yhigh-1)
                if any(self.is_contained((xc, yc), r) for r in noclick_regions):
                    removed += 1
                    continue
                e1 = spaces.PointerEvent(xc, yc, buttonmask=0) # release
                e2 = spaces.PointerEvent(xc, yc, buttonmask=1) # click
                e3 = spaces.PointerEvent(xc, yc, buttonmask=0) # release
                self._actions.append([e1, e2, e3])
        logger.info('noclick regions removed {} of {} actions'.format(removed, removed + len(self._actions)))
        self.action_space = gym.spaces.Discrete(len(self._actions))

    def _action(self, action_n):
        return [self._actions[int(action)] for action in action_n]

    @classmethod
    def is_contained(cls, point, coords):
        px, py = point
        x, width, y, height = coords
        return x <= px <= x + width and y <= py <= y + height


class SafeActionSpace(vectorized.Wrapper):
    """
    Recall that every universe environment receives a list of VNC events as action.
    There exist many environments for which the set of relevant action is much smaller
    and is known.   For example, Atari environments have a modest number of keys,
    so this wrapper, when applied to an Atari environment will reduce its action space.
    Doing so is very convenient for research, since today's RL algorithms rely on random
    exploration, which is hurt by small action spaces.  As our algorithms get better
    and we switch to using the raw VNC commands, this wrapper will become less important.


    NOTE: This class will soon be moved to `wrappers.experimental`. However the logic must currently remain in
    wrappers.SafeActionSpace in order to maintain backwards compatibility.
    """
    def __init__(self, env):
        super(SafeActionSpace, self).__init__(env)
        self._deprecation_warning()

        if self.spec.tags.get('runtime') == 'gym-core':
            self.action_space = gym_core_action_space(self.spec._kwargs['gym_core_id'])
        elif self.spec is None:
            pass
        elif self.spec.id in ['internet.SlitherIO-v0',
                              'internet.SlitherIOErmiyaEskandaryBot-v0',
                              'internet.SlitherIOEasy-v0']:
            self.action_space = spaces.Hardcoded([slither_vnc(left=True),
                                                  slither_vnc(right=True),
                                                  slither_vnc(space=True),
                                                  slither_vnc(left=True, space=True),
                                                  slither_vnc(right=True, space=True)])
        elif self.spec.id in ['flashgames.DuskDrive-v0']:
            # TODO: be more systematic
            self.action_space = spaces.Hardcoded([racing_vnc(up=True),
                                                  racing_vnc(left=True),
                                                  racing_vnc(right=True)])
        elif self.spec.id in ['flashgames.RedBeard-v0']:
            self.action_space = spaces.Hardcoded([platform_vnc(up=True),
                                                  platform_vnc(left=True),
                                                  platform_vnc(right=True),
                                                  platform_vnc(space=True)])

    def _deprecation_warning(self):
        logger.warn(('DEPRECATION WARNING: wrappers.SafeActionSpace has been moved to '
                     'wrappers.experimental.action_space.SafeActionSpace as of 2017-01-07. '
                     'Using legacy wrappers.SafeActionSpace will soon be removed'))
