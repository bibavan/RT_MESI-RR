import random
from prettytable import PrettyTable

# Параметры системы
NUM_PROCESSORS = 4
MEM_SIZE = 16  # 16 ячеек по 1 байт
CACHE_LINE_SIZE = 8  # Размер строки кэша 8 бит
CACHE_WAYS = 2  # Ассоциативность кэша 2
CACHE_SETS = 4  # 4 строки кэша

# Состояния строки кэша
INVALID = 0
SHARED = 1
EXCLUSIVE = 2
MODIFIED = 3
RECENT = 4
TAGGED = 5

states = {
    0: 'INVALID',
    1: 'SHARED',
    2: 'EXCLUSIVE',
    3: 'MODIFIED',
    4: 'RECENT',
    5: 'TAGGED'
}


# Класс строки кэша
class CacheLine:
    # линия кеша имеет тэг(адрес в главной памяти) дата(значение) и один из 6 стейтов
    def __init__(self):
        self.tag = 0
        self.data = 0
        self.state = INVALID


class MainMemory:
    # прост массив ячеек
    def __init__(self):
        self.data = [0] * MEM_SIZE


# Класс кэша
class Cache:
    # прост массив линий кэша
    def __init__(self):
        self.lines = [CacheLine() for _ in range(CACHE_SETS)]

    # возвращает линию с нужным тэгом
    def get_line(self, address):
        for line in self.lines:
            if line.state != INVALID and line.tag == address:
                return line
        return None


class Processor:
    global processors

    def __init__(self, id, cache, memory):
        # привязка с соответсвующему кэшу и к главной памяти
        self.id = id
        self.cache = cache
        self.main_memory = memory

    def rewrite_cacheline(self, tag, data, state):
        # если есть инвалидная строка - пишем в неё
        for line in self.cache.lines:
            if line.state == INVALID:
                line_to_write = line
                break
        else:
            # иначе радномную удаляем
            evicted_line = self.cache.lines[
                random.randint(0, CACHE_SETS - 1)]
            if evicted_line.state == TAGGED or evicted_line.state == MODIFIED:
                # сохраняем в мейн память если надо
                self.main_memory.data[evicted_line.tag] = evicted_line.data
                print(
                    f'evicted line {self.cache.lines.index(evicted_line)} with writing data to main memory')
            else:
                print(f'evicted line {self.cache.lines.index(evicted_line)}')
            evicted_line.state = INVALID
            line_to_write = evicted_line
        # записываем данные
        line_to_write.tag = tag
        line_to_write.data = data
        line_to_write.state = state

        # возвращает значение для чтения из других кэшей и флаг который надо к нему поставить

    def read_in_others(self, address):
        others_ids = list(range(NUM_PROCESSORS))
        others_ids.remove(self.id)
        # id всех кроме вызвашего
        for id in others_ids:
            line = processors[id].cache.get_line(address)
            if line is not None and line.state != SHARED:
                print(
                    f'CPU {id} interrupts and supplies data, because it has line {address} with state={states[line.state]}')
                if line.state == MODIFIED or line.state == TAGGED:
                    line.state = SHARED
                    return line.data, TAGGED
                if line.state == EXCLUSIVE or line.state == RECENT:
                    line.state = SHARED
                    return line.data, RECENT
        print('was not interrupted')
        return None, EXCLUSIVE

    # возвращает значение для модификации из других кэшей и флаг который надо к нему поставить
    def RWITM_in_others(self, address):
        others_ids = list(range(NUM_PROCESSORS))
        others_ids.remove(self.id)
        for id in others_ids:
            line = processors[id].cache.get_line(address)
            if line is not None and line.state != SHARED:
                print(
                    f'CPU {id} interrupts and supplies data, because it has line {address} with state={states[line.state]}')
                return line.data, MODIFIED
        print('was not interrupted')
        return None, RECENT

    # делает инвалидами все значения с заданным тэгом в других кэшах
    def invalidate_others(self, address):
        print(f'CPU {self.id} посылает запрос инвалидации')
        others_ids = list(range(NUM_PROCESSORS))
        others_ids.remove(self.id)
        for id in others_ids:
            line = processors[id].cache.get_line(address)
            if line is not None:
                print(
                    f'line {processors[id].cache.lines.index(line)} with tag {line.tag} in cache of CPU {processors[id].id} was invalidated: {states[line.state]}=>{INVALID} ')
                line.state = INVALID

    def read(self, address):
        print('log:')
        line = self.cache.get_line(address)
        # Read Hit
        if line is not None:
            print(
                f"Read hit: CPU {self.id} had line with tag {address} at line {self.cache.lines.index(line)}")
            return line.data
        # Read Miss
        print(
            f"Read miss: CPU {self.id} reads line {address} from main memory")
        data, state = self.read_in_others(address)
        # only in main memory
        if data is None:
            data = self.main_memory.data[address]
        # put data in cache
        self.rewrite_cacheline(address, data, state)
        return data

    def write(self, address):
        print('log:')
        line = self.cache.get_line(address)
        if line is not None:
            # write hit
            print(
                f'Write hit:CPU {self.id}  line {self.cache.lines.index(line)} with tag {address} at line ')
            data_0 = line.data
            state_0 = line.state
            line.data = (line.data + 1) % (2 ** CACHE_LINE_SIZE)
            if line.state != EXCLUSIVE and line.state != MODIFIED:
                self.invalidate_others(address)
            line.state = MODIFIED
            return f'Line {self.cache.lines.index(line)} with tag {line.tag}: {states[state_0]}=>{states[line.state]}, {data_0}=>{line.data} '

        # Промах в кэше
        print(f'Write miss: CPU {self.id} RWITM from main memory')
        data, state = self.RWITM_in_others(address)
        if data == None:
            data = self.main_memory.data[address]
        self.rewrite_cacheline(address, data + 1, MODIFIED)
        self.invalidate_others(address)
        return data


# Функция инициализации системы
def initialize_system():
    global processors, memory, time
    memory = MainMemory()
    processors = [Processor(i, Cache(), memory) for i in range(NUM_PROCESSORS)]


def user_interface():
    global processors, memory, time
    many = False
    while True:
        print("Команды:")
        print("r <processor_id> <address> - чтение по адресу")
        print("w <processor_id> <address>  - запись по адресу")
        if many:
            print('список команд на данный момент:')
            for i, command in enumerate(commands):
                print(f'{command} {processor_ids[i]} {addresses[i]}')
            print("m - закончить ввод нескольких команд")
        else:
            print("m - начать ввод нескольких команд")
        print("reset - сброс системы")
        print("exit - выход")

        command = input("Введите команду: ").split()

        if command[0] == "r":

            processor_id = int(command[1])
            address = int(command[2])
            if not many:
                data = processors[processor_id].read(address)
                print(
                    f"Процессор {processor_id} читает данные {data} из адреса {address}\n")
                print_system_state()
            else:
                if processor_id in processor_ids:
                    ans = input(
                        'Команда данному процессору уже была отдана, переписать? y/N:')
                    if ans == 'y' or ans == 'Y':
                        i = processor_ids.index(processor_id)
                        commands[i] = 'r'
                        addresses[i] = address
                else:
                    commands.append('r')
                    processor_ids.append(processor_id)
                    addresses.append(address)


        elif command[0] == "w":
            processor_id = int(command[1])
            address = int(command[2])
            if not many:
                processors[processor_id].write(address)
                print(
                    f"Процессор {processor_id} записывает данные в адрес {address}\n")
                print_system_state()
            else:
                if processor_id in processor_ids:
                    ans = input(
                        'Команда данному процессору уже была отдана, переписать? y/N:')
                    if ans == 'y' or ans == 'Y':
                        i = processor_ids.index(processor_id)
                        commands[i] = 'w'
                        addresses[i] = address
                else:
                    commands.append('w')
                    processor_ids.append(processor_id)
                    addresses.append(address)


        elif command[0] == "m":
            many = not many
            if many:
                commands = []
                processor_ids = []
                addresses = []
                print(
                    f"Вводите команды - по одной на процессор")
            else:
                print("Выполнение команд")
                for i, command in enumerate(commands):
                    print(f'{i}: {command} {processor_ids[i]} {addresses[i]}')
                    print(commands)
                    print(processor_ids)
                    print(addresses)
                    if command == 'r':
                        data = processors[processor_ids[i]].read(addresses[i])
                        print(
                            f"Процессор {processor_ids[i]} читает данные {data} из адреса {addresses[i]}")
                        print_system_state()
                    else:
                        processors[processor_ids[i]].write(addresses[i])
                        print(
                            f"Процессор {processor_ids[i]} записывает данные в адрес {addresses[i]}")
                        print_system_state()


        elif command[0] == "reset":
            initialize_system()
            many = False
            print("Система сброшена")

        elif command[0] == "exit":
            break

        else:
            print("Неизвестная команда")


# Функция вывода состояния системы
def print_system_state():
    global processors, memory, time
    print("Состояние системы:")
    print("Основная память:")
    mem = PrettyTable(list(range(MEM_SIZE)))
    mem.add_row(tuple(memory.data))
    print(mem)
    print("Кэши процессоров:")
    headers = tuple(f"Процессор {i}" for i in range(NUM_PROCESSORS))
    x = PrettyTable(headers)
    for line_id in range(CACHE_SETS):
        row = tuple()
        for i in range(NUM_PROCESSORS):
            line = processors[i].cache.lines[line_id]
            row += (
                f"Строка {line_id}: tag={line.tag}, data={line.data}, state={states[line.state]};",)
        x.add_row(row)
    print(x)


# Инициализация и запуск системы
initialize_system()
print_system_state()
user_interface()
