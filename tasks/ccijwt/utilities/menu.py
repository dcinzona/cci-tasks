from dataclasses import dataclass
from dataclasses import field
from typing import Callable, List, Optional, Dict

import rich

__all__ = ["menuUtil", "menu"]
KEYS_ENTER = (ord("\n"), ord("\r"))
KEYS_UP = ord("k")
KEYS_DOWN = ord("j")
KEYS_SELECT = ord(" ")

# =======================
#     MENUS FUNCTIONS
# =======================


@dataclass
class menuUtil:
    completekey = "enter"
    options: List[str]
    title: Optional[str] = None
    inputTextStr: str = "Enter Response: "
    defaultResponse: int = None
    inputIsNumber: bool = True
    indicator: str = "*"
    default_index: int = 0
    multiselect: bool = False
    min_selection_count: int = 0
    options_map_func: Optional[Callable[[str], str]] = None
    all_selected: List[str] = field(init=False, default_factory=list)
    custom_handlers: Dict[str, Callable[["menuUtil"], str]] = field(
        init=False, default_factory=dict
    )
    index: int = field(init=False, default=0)
    scroll_top: int = field(init=False, default=0)

    def __post_init__(self):
        self.console = rich.get_console()
        self.title = (
            f"\nPlease select an option [1-{len(self.options) + 1}]: "
            if self.title is None
            else self.title
        )

        if self.title.endswith(":") is False:
            # self.title = self.title + ": "
            pass
        if self.hasOptions():
            if len(self.options) == 0:
                raise ValueError("options should not be an empty list")

            if self.default_index >= len(self.options):
                raise ValueError(
                    "default_index should be less than the length of options"
                )

            if self.multiselect and self.min_selection_count > len(self.options):
                raise ValueError(
                    "min_selection_count is bigger than the available options, you will not be able to make any selection"
                )

            if self.options_map_func is not None and not callable(
                self.options_map_func
            ):
                raise ValueError("options_map_func must be a callable function")

        self.index = self.default_index

    def get_option_lines(self):
        lines = []
        if self.hasOptions():
            for index, option in enumerate(self.options):
                # pass the option through the options map of one was passed in
                if self.options_map_func:
                    option = self.options_map_func(option)

                if index == self.index:
                    prefix = self.indicator
                else:
                    prefix = len(self.indicator) * " "
                line = "{0} {1}".format(prefix, option)
                lines.append(line)

        return lines

    def get_title_lines():
        return []

    def get_lines(self):
        title_lines = self.get_title_lines()
        option_lines = self.get_option_lines()
        lines = title_lines + option_lines
        current_line = self.index + len(title_lines) + 1
        return lines, current_line

    def draw(self, invalidText=None):
        prompt = "{}\n".format(self.title)  # , '\n'.join(self.get_option_lines()))
        console = self.console
        with console.screen():
            console.clear()
            if self.hasOptions():
                for index, option in enumerate(self.options):
                    prompt += f"{index+1}. {option}" + "\n"

            if invalidText:
                prompt += f"\n[red]{invalidText}" + "\n"

            console.print(prompt)
            if self.hasOptions():
                selection = console.input(f"Select an option [1-{len(self.options)}]: ")
            else:
                selection = console.input(f"{self.inputTextStr}: ")

            return selection

    def hasOptions(self):
        return self.options and len(self.options) > 0

    def show(self, invalidText=None):
        selection = None
        try:
            selection = self.draw(invalidText=invalidText)
            return self.convertInputToType(selection)
        except Exception as e:
            print(e)
            return self.show(f'Invalid selection "{selection}"')

    def convertInputToType(self, selection):
        if selection == "" and self.defaultResponse is not None:
            selection = self.defaultResponse

        if self.hasOptions() and selection:
            return self.options[int(selection) - 1], selection

        if self.inputIsNumber and not isinstance(selection, int):
            return int(selection), selection

        return selection, selection

    def genericFunction(self, x):
        print(x)
        return True


def menu(*args, **kwargs):
    """Construct and start a :class:`Picker <Picker>`.
    Usage::
      >>> from utils.menu import menu
      >>> title = 'Please choose an option: '
      >>> options = ['option1', 'option2', 'option3']
      >>> responsePrompt = 'Enter a number (default is 1)'
      >>> defaultResponse = 1
      >>> option, index = menu(options, Optional[title, responsePrompt, defaultResponse])
    """
    picker = menuUtil(*args, **kwargs)
    return picker.show()
