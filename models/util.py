import random


class Bernoulli(object):
    def __init__(self, percentage):
        self.percentage = percentage

    def rand(self):
        return random.random() < self.percentage

    def random(self):
        return self.rand()
