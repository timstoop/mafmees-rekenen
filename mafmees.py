import os
from appdirs import *
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.progressbar import ProgressBar
from kivy.properties import NumericProperty, StringProperty
from kivy.clock import Clock
from kivy.animation import Animation
from random import randint

def get_save_path():
    if os.environ['ANDROID_APP_PATH']:
        return os.environ['ANDROID_APP_PATH']
    else:
        appname = "mafmees-rekenen"
        appauthor = "Tim Stoop"
        return user_data_dir(appname, appauthor)

class MafMeesRekenenLevel(Screen):
    score = NumericProperty(0)
    o1 = NumericProperty(0)
    o2 = NumericProperty(0)
    answer = StringProperty('')
    answered = False

    def on_enter(self, *args):
        self.make_level()

    def make_level(self, *args):
        self.ids['opgave'].color = [1, 1, 1, 1]
        self.o1 = randint(1,99)
        self.o2 = randint(1,99)
        self.answer = ''
        self.ids['progressbar'].value = 100
        self.ids['progressbar'].start_progress(self, 30)
        self.answered = False

    def press_num(self, num):
        """A number has been pressed, make sure that's visible."""
        if not self.answered and len(self.answer) < 4:
            self.answer += str(num)

    def press_bs(self):
        """Backspace has been pressed, remove the last character, if allowed."""
        if not self.answered and len(self.answer) > 0:
            self.answer = self.answer[:-1]

    def press_ok(self, *args):
        """Ok has been pressed, calculate result and score and the like."""
        if not self.answered:
            self.ids['progressbar'].stop_progress()
            self.answered = True
            if len(self.answer) > 0 and self.o1 + self.o2 == int(self.answer):
                self.answer_correct()
            else:
                self.answer_wrong()
            self.reset_event = Clock.schedule_once(self.make_level, 4)
        else:
            Clock.unschedule(self.reset_event)
            self.make_level()

    def answer_correct(self):
        self.ids['opgave'].color = [0, 1, 0, 1]
        self.score += 1

    def answer_wrong(self):
        self.ids['opgave'].color = [1, 0, 0, 1]
        if self.score > 0:
            self.score -= 1


class AnimProgressBar(ProgressBar):
    def start_progress(self, parent, length=30):
        Animation.cancel_all(self)
        anim = Animation(value=0, duration=length)
        anim.bind(on_complete=parent.press_ok)
        anim.start(self)

    def stop_progress(self):
        Animation.cancel_all(self)

    def on_complete(self):
        pass


class MafMeesMenu(Screen):
    pass

class MafMeesScreenManager(ScreenManager):
    pass

class MafMeesRekenenApp(App):
    def build(self):
        return MafMeesScreenManager()

if __name__ == '__main__':
    MafMeesRekenenApp().run()