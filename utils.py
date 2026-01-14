from math import dist

FONTS_PATH = "./UI/Fonts"

def obj_dist(obj1: object, obj2: object) -> float:
    """Returns the distance between 2 objects with x and y position properties"""
    return dist((obj1.x, obj1.y), (obj2.x, obj2.y))

class Anim:
    def __init__(self, obj: object, property: str, target: float, step: float, max_finish_dist: float) -> None:
        self.object = obj
        self.property = property
        self.target = target
        self.step = step
        self.max_finish_dist = max_finish_dist

        self.finished = False

        if not hasattr(self.object, self.property):
            raise Exception(f"Error while creating animation for {self.object}: {self.object} has no property \"{self.property}\"!")

    @property
    def gprop(self) -> float:
        return getattr(self.object, self.property)
    
    def sprop(self, value: float) -> None:
        setattr(self.object, self.property, value)

    def update(self, dt: float) -> bool:
        if abs(self.target - self.gprop) < max(self.step * dt, self.max_finish_dist):
            self.sprop(self.target)
            self.finished = True
            return True
        
        self.sprop(self.gprop + self.step * dt)
        return False

class AnimManager:
    def __init__(self) -> None:
        if not hasattr(self.__class__, "anims"):
            self.__class__.anims = []

    def new(self, obj: object, property: str, target: float, step: float, max_finish_dist: float = 0.5) -> Anim:
        anim = Anim(obj, property, target, step, max_finish_dist)
        self.anims.append(anim)

        return anim

    def update(self, dt: float) -> None:
        complete_anims = []

        for anim in self.anims:
            done = anim.update(dt)

            if done:
                complete_anims.append(anim)

        for anim in complete_anims:
            self.anims.remove(anim)