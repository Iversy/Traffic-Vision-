from collections import defaultdict, deque
from functools import partial

import cv2
import numpy as np
from ultralytics import YOLO
from ultralytics.engine.results import Results

from Debug_drawer import draw_debug
from misc import Location
from People import People, State, parse_results


class Tracking:
    def __init__(self) -> None:
        self.image_width = 1920
        self.image_height = 1080
        self.id_state = dict()
        self.id_location: dict[int, State] = dict()
        self.predict_history = np.empty(10, dtype=Results)

    def process_video_with_tracking(self, model: YOLO, video_path: str, show_video=True, save_path=None):
        save_video = save_path is not None
        out = None

        model_args = {"iou": 0.4, "conf": 0.5, "persist": True,
                      "imgsz": 640, "verbose": False,
                      "tracker": "botsort.yaml",
                      "vid_stride": 7}

        for frame_number, results in enumerate(model.track(video_path, stream=True, **model_args)):
            if save_video:
                if out is None:
                    fps = 25
                    shape = results.orig_shape
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(save_path, fourcc, fps, shape)
                out.write(results.plot())

            if show_video:
                frame = draw_debug(results, draw_lines=False)
                cv2.imshow("frame", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            self.tracking(results)

            # TODO: Замах на будущее
            # self.predict_history[frame_number % 10] = results
            #
            # if frame_number % 100 == 0 and frame_number != 0:
            #     self._tracking()

        if save_video:
            out.release()
        cv2.destroyAllWindows()
    
    def tracking(self, results: Results):
        # TODO: этот код нужно поделить на методы, каждый методы (зашел вышел прошел)
        for person in parse_results(results):
            now = person.check_how_close_to_door()
            if person.id_person not in self.id_location:
                newborn = now is Location.Close
                self.id_location[person.id_person] = State(now, newborn)
                if newborn:
                    print("Я родился!", person)
                continue
            state = self.id_location[person.id_person]
            before = state.location
            if now is Location.Close and before is Location.Around:
                print("Я вышел!", person)
            if not state.newborn and now is Location.Around and before is Location.Close:
                print("Погодите-ка, я просто мимо проходил", person)
            self.id_location[person.id_person].update(now)

    def _tracking(self):
        # TODO: Так будет работать логика будущего, сначала парсинг result, потом парсинг массива каждым методом
        frame_objects = np.empty(10, dtype=object)
        for i, frame_result in enumerate(self.predict_history):
            frame_objects[i] = parse_results(frame_result)

        # self.people_coming(person)
        # self._people_leave(frame_objects)
    def _door_touch(self, person: People, code: int) -> None:
        """
        Выводит в консоль сообщение о том что человек вошёл в дверь, информацию о человеке
        :param person: Человек и его данные
        :type person: People
        :param code: код, возвращаемый People.check_how_close_to_door
        :type code: int
        :return: Ничего
        :rtype: None
        """
        if code is not Location.Close or self.id_state[person.get_person_id()]:
            return
        self.id_state[person.get_person_id()] = True
        print("Человек вошёл в дверь")
        person.print_person()


if __name__ == "__main__":
    pass