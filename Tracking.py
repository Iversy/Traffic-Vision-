import cv2
import numpy as np
from cv2.typing import MatLike
from ultralytics import YOLO
from ultralytics.engine.results import Results

from Doors import Doors
from misc import Distances, Location, boxes_center
from People import People


class Tracking:
    def __init__(self) -> None:
        self.image_width = 1920
        self.image_height = 1080
        self.id_state = dict()
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
                frame = self._draw_debug(results, draw_boxes=True, draw_lines=False)
                cv2.imshow("frame", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            self.predict_history[frame_number % 10] = results

            if frame_number % 10 == 0 and frame_number != 0:
                self._tracking()

        if save_video:
            out.release()
        cv2.destroyAllWindows()

    def _tracking(self):
        frame_objects = np.empty(10, dtype=object)
        for i, frame_result in enumerate(self.predict_history):
            frame_objects[i] = self.parse_results(frame_result)

        # self.people_coming(person)
        # self._people_leave(frame_objects)
        self._door_touch(frame_objects)

    @staticmethod
    def _people_leave(peoples_from_frame):
        # Вот так можно обходить
        for frame_object in peoples_from_frame:
            for person in frame_object:
                location_person = person.check_how_close_to_door()
                if location_person == Location.Around:
                    print("Человек находится рядом с дверной рамой")
                elif location_person == Location.Close:
                    print("Человек находится внутри дверной рамы")
                else:
                    print("Человек находится далеко от двери")

    def _people_coming(self, person: People):
        id_person = person.get_person_id()
        if not self.id_state.get(id_person):
            self.id_state[id_person] = False
        code = person.check_how_close_to_door()  # сохраняем код с функции
        self._door_touch(person, code)  # смотрим если человек вошёл в дверь

    def _door_touch(self, peoples_from_frame) -> None:
        person_door_relationship = dict()
        for frame_object in peoples_from_frame:
            for person in frame_object:
                person_id = person.get_person_id()
                location_person = person.check_how_close_to_door()
                if not person_door_relationship.get(person_id):
                    person_door_relationship[person_id] = location_person
                    continue
                last_location = person_door_relationship[person_id]
                if last_location == Location.Far and location_person == Location.Close:
                    print("Мама что произошло за за 7 фреймов") #Смотрим случай когда за 7 кадров человек улетел куда-то
                elif last_location == Location.Around and location_person == Location.Close:
                    print("Человек вошёл в дверь")
                    person.print_person()
                elif last_location == Location.Close and location_person == Location.Around:
                    print("Человек вышел из двери")
                    person.print_person()
                elif last_location == Location.Close and location_person == Location.Far:
                    print("Мама что произошло за за 7 фреймов")
                person_door_relationship[person_id] = location_person


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
    def _draw_debug(self, results: Results,
                    draw_boxes=True, draw_doors=True, draw_lines=True) -> MatLike:
        frame = results.orig_img
        if draw_boxes:
            frame = results.plot()
        if draw_lines:
            self._line_door_person(frame, results)
        if draw_doors:
            self._draw_doors(frame)
        return cv2.resize(frame, (0, 0), fx=0.75, fy=0.75)

    @staticmethod
    def _draw_doors(frame: MatLike):
        for door in Doors:
            x, y = door.center
            r = 10
            pt1 = door.corners[:2]
            pt2 = door.corners[2:]
            cv2.rectangle(frame, pt1, pt2, color=(255, 255, 255))
            cv2.circle(frame, (x, y), radius=Distances.Close, color=(0, 0, 255))
            cv2.circle(frame, (x, y), radius=Distances.Around, color=(0, 255, 0))
            # cv2.circle(frame, (x, y), radius=r, color=(0, 0, 255),
            #            thickness=-1)
            cv2.putText(frame, door.name[0], org=(x - r, y - r * 2),
                        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                        fontScale=1, color=(255, 255, 255),
                        thickness=2)

    def _line_door_person(self, frame: np.ndarray, results: Results, coef: float = 1) -> None:
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
