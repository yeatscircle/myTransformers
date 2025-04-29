#!/usr/bin/env python
# Copyright 2020 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from myTransformers import HfArgumentParser
from myTransformers.commands.add_fast_image_processor import AddFastImageProcessorCommand
from myTransformers.commands.add_new_model_like import AddNewModelLikeCommand
from myTransformers.commands.chat import ChatCommand
from myTransformers.commands.convert import ConvertCommand
from myTransformers.commands.download import DownloadCommand
from myTransformers.commands.env import EnvironmentCommand
from myTransformers.commands.run import RunCommand
from myTransformers.commands.serving import ServeCommand


def main():
    parser = HfArgumentParser(prog="Transformers CLI tool", usage="myTransformers-cli <command> [<args>]")
    commands_parser = parser.add_subparsers(help="myTransformers-cli command helpers")

    # Register commands
    ChatCommand.register_subcommand(commands_parser)
    ConvertCommand.register_subcommand(commands_parser)
    DownloadCommand.register_subcommand(commands_parser)
    EnvironmentCommand.register_subcommand(commands_parser)
    RunCommand.register_subcommand(commands_parser)
    ServeCommand.register_subcommand(commands_parser)
    AddNewModelLikeCommand.register_subcommand(commands_parser)
    AddFastImageProcessorCommand.register_subcommand(commands_parser)

    # Let's go
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        exit(1)

    # Run
    service = args.func(args)
    service.run()


if __name__ == "__main__":
    main()
