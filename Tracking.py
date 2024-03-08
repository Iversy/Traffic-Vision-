import cv2
import numpy as np
from cv2.typing import MatLike
from ultralytics import YOLO
from ultralytics.engine.results import Results

from Doors import Doors
from misc import Location, boxes_center
from People import People


class Tracking:
    def __init__(self) -> None:
        self.image_width = 1920
        self.image_height = 1080
        self.id_state = dict()

    def people_leave(self, person: People):
        location_person = person.check_how_close_to_door()
        if location_person is Location.Around:
            print("Человек находится рядом с дверной рамой")
        elif location_person is Location.Close:
            print("Человек находится внутри дверной раме")
        else:
            print("Человек находится далеко от двери")

    def process_video_with_tracking(self, model: YOLO, video_path: str, show_video=True, save_path=None):
        save_video = save_path is not None
        out = None

        model_args = {"iou": 0.4, "conf": 0.5, "persist": True,
                      "imgsz": 640, "verbose": False,
                      "tracker": "botsort.yaml",
                      "vid_stride": 3}

        for frame_number, results in enumerate(model.track(video_path, stream=True, **model_args)):
            if save_video:
                if out is None:
                    fps = 25
                    shape = results.orig_shape
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(save_path, fourcc, fps, shape)
                out.write(results.plot())

            if show_video:
                frame = self.draw_debug(results, draw_boxes=False)
                cv2.imshow("frame", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            self._tracking(results)

        if save_video:
            out.release()
        cv2.destroyAllWindows()

    def _tracking(self, results):
        people_objects = self.parse_results(results)

        for person in people_objects:
            if not self.id_state.get(person.get_person_id()):
                self.id_state[person.get_person_id()] = False
            code = person.check_how_close_to_door()  # сохраняем код с функции
            self.door_touch(person, code)  # смотрим если человек вошёл в дверь

    @staticmethod
    def parse_results(results: Results) -> list[People]:
        """
        Создаёт список объектов People на основе result

        :param results: Результат обнаружения объектов
        :type results: Results
        :return: Список объектов People
        :rtype: list[People]
        """
        if results.boxes.id is None:
            return list()
        boxes = results.boxes.numpy()
        centers = boxes_center(boxes.xyxy)
        people = list()
        for box, center in zip(boxes, centers.astype(int)):
            people.append(People(*box.id, int(*box.cls), *box.conf, tuple(center)))
        return people

    # region Интерактивное отображение дверей и векторов
    def draw_debug(self, results: Results,
                   draw_boxes=True, draw_doors=True, draw_lines=True) -> MatLike:
        frame = results.orig_img
        if draw_boxes:
            frame = results.plot()
        if draw_lines:
            self.line_door_person(frame, results)
        if draw_doors:
            self.draw_doors(frame)
        return cv2.resize(frame, (0, 0), fx=0.75, fy=0.75)

    @staticmethod
    def draw_doors(frame: MatLike):
        for door in Doors:
            x, y = door.center
            r = 10
            pt1 = door.corners[:2]
            pt2 = door.corners[2:]
            cv2.rectangle(frame, pt1, pt2, color=(0, 0, 255))
            cv2.circle(frame, (x, y), radius=r, color=(0, 0, 255),
                       thickness=-1)
            cv2.putText(frame, door.name[0], org=(x - r, y - r * 2),
                        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                        fontScale=1, color=(255, 255, 255),
                        thickness=2)

    def line_door_person(self, frame: np.ndarray, results: Results, coef: float = 1) -> None:
        """
        Рисует линии от человека к 3м дверям, обращаясь к координатам из enum Doors

        :param frame: Кадр из записи для обработки
        :type frame: np.ndarray
        :param results: Результат обнаружения объектов
        :type results: Results
        :param coef: Коэффициент масштабирования изображения
        :type coef: float
        :return: Ничего
        :rtype: None
        """
        people_objects = self.parse_results(results)
        for person in people_objects:
            for door in Doors.centers:
                cv2.line(frame, person.position, door, 
                         color=(102, 255, 51), thickness=5)

    # endregion

    def door_touch(self, person: People, code: Location) -> None:
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
