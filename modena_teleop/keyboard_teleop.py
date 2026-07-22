import rclpy
from rclpy.node import Node
import sys
import select
import tty
import termios
from modena_common.enums import JogType, JogIndex, JogDirection
from modena_interfaces.msg import JogCmd
from modena_interfaces.msg import RobotState


class KeyboardTeleop(Node):
    def __init__(self):
        super().__init__("keyboard_teleop")

        # Publishes current pressed key
        self.jog_cmd_pub = self.create_publisher(JogCmd, "jog_cmd", 10)
        
        # Subscribes to receive robot states
        self.robot_state_sub = self.create_subscription(RobotState, "robot_state", self.robot_state_callback, 10)
        
        # Current robot state
        self.joint_pos = None
        self.tool_pose = None        

        # Handle initial press delay
        self.total_iterations = 10
        self.counter = self.total_iterations
        self.first_press = False
        self.latch = False
        self.last_key = ""

        # Initial jogging parameters
        self.jog_speed = 50
        self.speed_incr = 5
        self.jog_type = JogType.JOG_JOINT      
        self.jog_type_str = "Joint"

        # Saves original terminal settings
        self.original_settings = termios.tcgetattr(sys.stdin)

        # Terminal settings
        self.settings = termios.tcgetattr(sys.stdin)

        # Forces echo off in saved settings
        self.settings[3] &= ~(termios.ECHO | termios.ECHONL)
        
        # Hides cursor
        print("\033[?25l", end="", flush=True)

        # Runs keyboard polling and updates display at 20 Hz
        self.create_timer(0.05, self.keyboard_loop)      
        
    def robot_state_callback(self, msg):
        self.joint_pos = msg.joint_pos
        self.tool_pose = msg.tool_pose
        
    def update_display(self):           
        sys.stdout.write("\033[2J\033[3J\033[H\033[?25l")
        sys.stdout.flush()
        
        output = (
        "========================================\n"
        "       MR-3 Mini Keyboard Teleop\n"
        "========================================\n\n"
        f"Mode      : {self.jog_type_str}\n"
        f"Jog speed : {self.jog_speed}%\n\n"
        )
        
        if self.tool_pose is not None:
            output += (
                "Tool pose:\n"
                f"X : {self.tool_pose[0]:.2f} mm\n"
                f"Y : {self.tool_pose[1]:.2f} mm\n"
                f"Z : {self.tool_pose[2]:.2f} mm\n"
                f"R : {self.tool_pose[3]:.2f}°\n\n"
            )
        
        if self.joint_pos is not None:
            output += (
                "Joint positions:\n"
                f"J1 : {self.joint_pos[0]:.2f}°\n"
                f"J2 : {self.joint_pos[1]:.2f}°\n"
                f"J3 : {self.joint_pos[2]:.2f}°\n"
                f"J4 : {self.joint_pos[3]:.2f}°\n\n"
            )

        output += ("Controls:\n"
                   "W: +J1 | +X\n"
                   "S: -J1 | -X\n"
                   "D: +J2 | +Y\n"
                   "A: -J2 | -Y\n"
                   "E: +J3 | +Z\n"
                   "Q: -J3 | -Z\n"
                   "2: +J4 | +R\n"
                   "1: -J4 | -R\n\n"
                   "F: switch between JOINT, WORLD, and TOOL jog modes\n"
                   "+: increase jog speed by 5%\n"
                   "-: decrease jog speed by 5%\n"
                   "\nPress Ctrl+C to quit\n\n"
                )       

        sys.stdout.write(output)
        sys.stdout.flush()  
    
    def switch_jog_mode(self):
        if self.jog_type == JogType.JOG_JOINT:
            self.jog_type = JogType.JOG_WORLD
            self.jog_type_str = "World"

        elif self.jog_type == JogType.JOG_WORLD:
            self.jog_type = JogType.JOG_TOOL
            self.jog_type_str = "Tool"

        elif self.jog_type == JogType.JOG_TOOL:
            self.jog_type = JogType.JOG_JOINT
            self.jog_type_str = "Joint"

    def get_key(self):
        fd = sys.stdin.fileno()

        tty.setraw(fd)

        settings = termios.tcgetattr(fd)
        settings[3] |= termios.ISIG # enables Ctrl + C

        termios.tcsetattr(fd, termios.TCSANOW, settings)

        rlist, _, _ = select.select([sys.stdin], [], [], 0.05)

        if rlist:
            key = sys.stdin.read(1) # single character
        else:
            key = "" # timeout → release
        
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings) # restore settings immediately (important!)
        return key

    def press_delay_handler(self):
        if not self.latch:
            if not self.first_press: # first press case
                self.first_press = True
                self.counter = self.total_iterations

    def build_msg(self, index, dir):
        msg = JogCmd()

        msg.type = self.jog_type
        msg.index = index
        msg.speed = self.jog_speed
        msg.dir = dir

        return msg

    def build_stop_msg(self):
        msg = JogCmd()

        msg.type = JogType.JOG_NONE
        msg.index = 0
        msg.speed = 0
        msg.dir = 0

        return msg

    def increase_jog_speed(self):
        if self.jog_speed >= 100:
            return False

        self.jog_speed += self.speed_incr
        self.jog_speed = max(1, min(self.jog_speed, 100))

        # Handle case when increasing from 1%
        if self.jog_speed == 6:
            self.jog_speed = 5

        return True

    def decrease_jog_speed(self):
        if self.jog_speed <= 1:
            return False

        self.jog_speed -= self.speed_incr
        self.jog_speed = max(1, min(self.jog_speed, 100))

        return True

    def keyboard_loop(self):
        key = self.get_key()

        # Handle initial press delay case where the read key is '' even when another key is being pressed
        if self.first_press:
            key = self.last_key
            self.counter -= 1

            if self.counter == 0:
                self.first_press = False
                self.latch = True

        # Key mapping
        if key == "w":  # +J1 / +X
            msg = self.build_msg(JogIndex.JOG_INDEX_1, JogDirection.JOG_POS)
            self.press_delay_handler()

        elif key == "s":  # -J1 / -X
            msg = self.build_msg(JogIndex.JOG_INDEX_1, JogDirection.JOG_NEG)
            self.press_delay_handler()

        elif key == "d":  # +J2 / +Y
            msg = self.build_msg(JogIndex.JOG_INDEX_2, JogDirection.JOG_POS)
            self.press_delay_handler()

        elif key == "a":  # -J2 / -Y
            msg = self.build_msg(JogIndex.JOG_INDEX_2, JogDirection.JOG_NEG)
            self.press_delay_handler()

        elif key == "e":  # +J3 / +Z
            msg = self.build_msg(JogIndex.JOG_INDEX_3, JogDirection.JOG_POS)
            self.press_delay_handler()

        elif key == "q":  # -J3 / -Z
            msg = self.build_msg(JogIndex.JOG_INDEX_3, JogDirection.JOG_NEG)
            self.press_delay_handler()

        elif key == "2":  # +J4 / +R
            msg = self.build_msg(JogIndex.JOG_INDEX_4, JogDirection.JOG_POS)
            self.press_delay_handler()

        elif key == "1":  # -J4 / -R
            msg = self.build_msg(JogIndex.JOG_INDEX_4, JogDirection.JOG_NEG)
            self.press_delay_handler()

        else:
            msg = self.build_stop_msg()

            if key == "f" and self.last_key != "f":
                self.switch_jog_mode()
                self.press_delay_handler()
                
            elif key == "+":
                self.increase_jog_speed()

            elif key == "-":
                self.decrease_jog_speed()               
                    
            else:  # any other key (including empty)
                if self.latch:
                    self.latch = False

        self.last_key = key
        self.jog_cmd_pub.publish(msg)
        
        self.update_display()      

    def destroy_node(self):
        try:      
            print("\033[?25h", end="", flush=True)                                  # shows cursor again
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.original_settings) # restores terminal on shutdown
        except Exception:
            pass  # ignore errors if terminal is already closed

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    node = KeyboardTeleop()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass  # Ctrl + C received: shuts down cleanly
    except Exception as e:
        node.get_logger().error(f"Unexpected error: {e}")
    finally:
        node.destroy_node()
        
        if rclpy.ok():              
            rclpy.shutdown()        


if __name__ == "__main__":
    main()
