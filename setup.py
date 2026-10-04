from setuptools import find_packages, setup

package_name = 'modena_teleop'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Matheus Lino',
    maintainer_email='matheus.vlino@gmail.com',
    description='ROS 2 teleoperation tools for Modena robots',
    license='BSD-3-Clause',
    entry_points={
        'console_scripts': [
            'keyboard_teleop = modena_teleop.keyboard_teleop:main'
        ],
    },
)