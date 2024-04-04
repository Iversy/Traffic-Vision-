from datetime import datetime, timedelta
from enum import Enum
from itertools import product
from time import mktime
from typing import Sequence

import numpy as np
import pandas as pd
import redis


class Action(Enum):
    Enter = "enter"
    Exit = "exit"

class Gender(Enum):
    Man = "man"
    Woman = "woman"
    Kid = "kid"

class Filter:
    def __init__(self, action: Action|tuple[Action]=None, gender: Gender|tuple[Gender]=None) -> None:
        self.actions = self.parse(action, Action)
        self.genders = self.parse(gender, Gender)

    def parse(self, something, anything: Enum) -> tuple[Enum]:
        if something is None:
            something = tuple(anything)
        if not isinstance(something, Sequence):
            something = (something, )
        return something
    
    def tuple_to_str(self, s: tuple[Enum]) -> str:
        if len(s) == 1:
            return s[0].value
        return f"({','.join(e.value for e in s)})"
    
    def filter(self) -> list[str]:
        a = [f"action={self.tuple_to_str(self.actions)}", 
             f"gender={self.tuple_to_str(self.genders)}"]
        print(a)
        return a
    
    def __str__(self) -> str:
        return f"Filter {self.actions}, {self.genders}"


unix_timestamp = int


def datetime_to_unix(time: datetime) -> unix_timestamp:
    return int(mktime(time.timetuple()) * 1000)


def unix_to_datetime(time: int) -> datetime:
    return datetime.fromtimestamp(time / 1000)


class Redis:
    people_key = "ts_people"

    def __init__(self) -> None:
        self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.timeseries = self.redis.ts()
    
    def key(self, action: Action, gender: Gender) -> str:
        return f"{self.people_key}:{action.value}:{gender.value}"
    
    def labels(self, action: Action, gender: Gender) -> dict[str, str]:
        return {"action": action.value, "gender": gender.value, "oleg": "pepeg"}

    def get_count(self, start: datetime, end: datetime,
                  action: Action, step: int) -> dict[str, list[tuple[unix_timestamp, int]]]:
        "deprecated, don't use it"
        start, end = map(datetime_to_unix, (start, end))
        bucket = int(step * 1000)

        data = self.timeseries.mrange(start, end, [f"action={action}"], empty=True,
                                      aggregation_type="last", bucket_size_msec=bucket)
        res = dict()
        for (name, value), *_ in map(dict.items, data):
            _, _, gender = name.rpartition(":")
            res[gender] = value[1]
        return res

    def get_hist(self, date: datetime, n_buckets: int, filter: Filter=None) -> pd.DataFrame:
        """
        Возвращает количество человек в день date с шагом 24/n_buckets часов.

        :param date: Дата
        :type date: datetime
        :param n_buckets: Число строчек таблицы
        :type n_buckets: int
        :param filter: Фильтр действия и пола, defaults to None
        :type filter: Filter, optional
        :return: Таблица где индекс - datetime время, колонки - action, gender
        :rtype: pd.DataFrame
        """
        filter = filter or Filter()
        day_start = datetime_to_unix(date.date())
        day_lenght = int(timedelta(days=1).total_seconds()*1000)
        day_end = day_start + day_lenght
        bucket = day_lenght // n_buckets
        
        response = self.timeseries.mrange(day_start, day_end-1, filter.filter(),
                                          aggregation_type="range", bucket_size_msec=bucket,
                                          align="-")
        index = pd.date_range(date.date(), unix_to_datetime(day_end), n_buckets+1, inclusive="left")
        actions = filter.actions
        genders = filter.genders

        columns = pd.MultiIndex.from_product((actions, genders))
        result = pd.DataFrame(0, index=index, columns=columns)
        
        for part in response:
            (full_name, raw_data), *_ = part.items()
            _, act, gen = full_name.split(":")
            act, gen = Action(act), Gender(gen)
            for time, count in raw_data[1]:
                time = unix_to_datetime(time)
                result.at[time, (act, gen)] = count
        return result

    def last_update(self, action: Action, gender: Gender) -> datetime:
        if not self.redis.exists(self.key(action, gender)):
            return datetime.now()
        time, _ = self.timeseries.get(self.key(action, gender))
        return unix_to_datetime(time)
    
    def reset_counter(self, action: Action, gender: Gender, time: datetime):
        if self.last_update(action, gender).day == time.day:
            return
        print("I am gona reset counter!")
        time = datetime_to_unix(time.date())
        self.timeseries.add(self.key(action, gender), time, 0,
                            labels=self.labels(action, gender))

    def increment(self, action: Action, gender: Gender, time: datetime):
        self.reset_counter(action, gender, time)
        time = datetime_to_unix(time)
        self.timeseries.incrby(self.key(action, gender), 1, time,
                               labels=self.labels(action, gender))

    def decrement(self, action: Action, gender: Gender, time: datetime):
        self.reset_counter(action, gender, time)
        time = datetime_to_unix(time)
        self.timeseries.decrby(self.key(action, gender), 1, time,
                               labels=self.labels(action, gender))

    def remove_all_data(self, force=False):
        if force or input("Вы уверенны что хотите удалить все данные из базы? [y/n]: ") == 'y':
            for key in self.redis.scan_iter("*"):
                self.redis.delete(key)
            return
        print("Отмена")

    def create_test_data(self):
        if input("Вы уверенны что хотите наполнить базу фальшивыми данными? [y/n]: ") != 'y':
            print("Отмена")
            return
        np.random.seed(1)
        self.remove_all_data(True)
        center = datetime_to_unix(datetime(2024, 3, 15, 12))
        spread = 5*3600*1000

        for action, gender in product(Action, Gender):
            times = np.random.normal(center, spread, size=1000)
            times = np.unique(times)

            for t in times:
                self.increment(action, gender, unix_to_datetime(t))


if __name__ == "__main__":
    from matplotlib import pyplot as plt
    db = Redis()
    db.create_test_data()

    res = db.get_hist(datetime(2024, 3, 15, 12), 12)
    print(res)
    print()
    res.plot(kind='bar')
    plt.xticks(rotation=45, ha='right')
    plt.show()

