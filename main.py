#!/usr/bin/env python3

import sys
import os
from time import sleep
import threading

from game import *


def main():
    # start mill game:
    game = Game()
    game.run_game()


if __name__ == "__main__":
    main()
