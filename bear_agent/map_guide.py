"""
地图问路模块
每个地名是一个结点，相邻地点是带估算权重和方位描述的边。
问路时随机设置熊大当前位置，并用 Dijkstra 计算带权最短路线。
结构化字段 destination / path / path_world 来自 poi_registry.json（与 Unity 3D 坐标对齐）。
"""
import heapq
import os

from poi_registry import get_place_world, load_poi_registry, path_world as registry_path_world


class MapGuide:
    """根据游客语音里的地点关键词返回问路回答。"""

    DEFAULT_START = "方特城堡"

    ALIASES = {
        "方特城堡": ["方特城堡", "城堡"],
        "游客服务中心": ["游客服务中心", "服务中心"],
        "熊出没折扣店": ["熊出没折扣店", "折扣店"],
        "熊出没旗舰店": ["熊出没旗舰店", "旗舰店"],
        "寄存室": ["寄存室", "寄存处", "寄存"],
        "售票处": ["售票处", "售票"],
        "代步车": ["代步车", "租车"],
        "魔法城堡": ["魔法城堡"],
        "许愿树": ["许愿树"],
        "聊斋": ["聊斋"],
        "电影科技大揭秘": ["电影科技大揭秘", "电影科技", "大揭秘"],
        "海螺湾": ["海螺湾"],
        "梦幻广场": ["梦幻广场", "广场"],
        "逃出恐龙岛": ["逃出恐龙岛", "恐龙岛"],
        "唐古拉雪山": ["唐古拉雪山", "雪山"],
        "东关削面王": ["东关削面王", "削面王"],
        "生命之光": ["生命之光"],
        "宇宙博览会": ["宇宙博览会", "宇宙馆"],
        "飞越极限": ["飞越极限"],
        "双层转马": ["双层转马", "转马", "旋转木马"],
        "高空飞翔": ["高空飞翔"],
        "华夏五千年": ["华夏五千年"],
        "临水餐厅": ["临水餐厅", "餐厅"],
        "火流星": ["火流星"],
        "吉祥馄饨": ["吉祥馄饨", "馄饨"],
        "熊出没脱口秀": ["熊出没脱口秀", "脱口秀"],
        "熊出没历险记": ["熊出没历险记", "历险记"],
        "恐龙飞车": ["恐龙飞车", "恐龙车"],
        "德克士": ["德克士"],
        "童梦天地": ["童梦天地"],
        "疯狂成语": ["疯狂成语", "成语"],
        "飓风飞椅": ["飓风飞椅", "飞椅"],
        "大摆锤": ["大摆锤"],
        "空中飞舞": ["空中飞舞"],
        "海盗船": ["海盗船"],
        "波浪翻滚": ["波浪翻滚"],
        "超级救火队": ["超级救火队", "救火队"],
        "海马骑兵": ["海马骑兵"],
        "熊熊海盗船": ["熊熊海盗船"],
        "欢乐滑车": ["欢乐滑车", "滑车"],
        "欢乐袋鼠": ["欢乐袋鼠"],
        "嘟嘟小车": ["嘟嘟小车", "小车"],
        "小奇兵": ["小奇兵"],
        "冰雪列车": ["冰雪列车", "列车"],
    }

    # 权重是按地图道路相邻关系粗略估算的步行距离，数值越小表示越近。
    # 只连接地图上沿道路相邻的地点，避免跨湖或跨区域直接连边。
    EDGES = [
        ("方特城堡", "飓风飞椅", 2),
        ("方特城堡", "熊出没旗舰店", 2),
        ("方特城堡", "熊出没折扣店", 3),
        ("熊出没旗舰店", "电影科技大揭秘", 1),
        ("方特城堡", "电影科技大揭秘", 3),
        ("方特城堡", "大摆锤", 2),

        ("游客服务中心", "售票处", 2),
        ("游客服务中心", "代步车", 1),
        ("游客服务中心", "熊出没折扣店", 2),
        ("游客服务中心", "大摆锤", 2),
        ("售票处", "寄存室", 3),
        ("寄存室", "熊出没旗舰店", 2),
        ("寄存室", "聊斋", 3),

        ("熊出没折扣店", "游客服务中心", 2),
        ("熊出没折扣店", "方特城堡", 2),
        ("熊出没折扣店", "熊出没旗舰店", 2),
        ("熊出没旗舰店", "电影科技大揭秘", 1),
        ("电影科技大揭秘", "聊斋", 1),
        ("电影科技大揭秘", "海螺湾", 2),

        ("聊斋", "魔法城堡", 3),
        ("许愿树", "魔法城堡", 0.5),
        ("许愿树", "海螺湾", 1),
        ("海螺湾", "梦幻广场", 0.5),
        ("梦幻广场", "唐古拉雪山", 2),
        ("梦幻广场", "逃出恐龙岛", 2),
        ("唐古拉雪山", "逃出恐龙岛", 2),
        ("唐古拉雪山", "东关削面王", 2),
        ("唐古拉雪山", "生命之光", 3),

        ("生命之光", "宇宙博览会", 1),
        ("宇宙博览会", "飞越极限", 1),
        ("宇宙博览会", "双层转马", 1),
        ("飞越极限", "高空飞翔", 2),
        ("飞越极限", "华夏五千年", 1),
        ("高空飞翔", "华夏五千年", 1),
        ("高空飞翔", "双层转马", 1),

        ("双层转马", "临水餐厅", 2),
        ("双层转马", "吉祥馄饨", 3),
        ("临水餐厅", "火流星", 2),
        ("火流星", "吉祥馄饨", 1),
        ("火流星", "飓风飞椅", 3),
        ("吉祥馄饨", "熊出没脱口秀", 1),
        ("熊出没脱口秀", "熊出没历险记", 2),

        ("熊出没历险记", "恐龙飞车", 2),
        ("熊出没历险记", "德克士", 2.5),
        ("恐龙飞车", "超级救火队", 2),
        ("恐龙飞车", "熊熊海盗船", 2),
        ("熊熊海盗船", "海马骑兵", 2),
        ("熊熊海盗船", "小奇兵", 2),
        ("超级救火队", "海马骑兵", 2),
        ("海马骑兵", "欢乐滑车", 2),
        ("欢乐滑车", "欢乐袋鼠", 1),
        ("欢乐袋鼠", "嘟嘟小车", 1),
        ("嘟嘟小车", "冰雪列车", 1),
        ("冰雪列车", "小奇兵", 1),
        ("小奇兵", "恐龙飞车", 2),
        ("德克士", "童梦天地", 2),
        ("童梦天地", "疯狂成语", 2),
        ("童梦天地", "飓风飞椅", 3),
        ("疯狂成语", "波浪翻滚", 2),
        ("疯狂成语", "海盗船", 2),

        ("飓风飞椅", "大摆锤", 2),
        ("飓风飞椅", "空中飞舞", 2),
        ("飓风飞椅", "方特城堡", 2),
        ("空中飞舞", "大摆锤", 2),
        ("空中飞舞", "海盗船", 2),
        ("海盗船", "波浪翻滚", 1),
        ("波浪翻滚", "疯狂成语", 2),
    ]

    # 每条无向边只写一个方向，反方向会自动取相反方位。
    EDGE_DIRECTIONS = {
        ("方特城堡", "飓风飞椅"): "往东南走",
        ("方特城堡", "熊出没旗舰店"): "往东北走",
        ("方特城堡", "熊出没折扣店"): "往西北走",
        ("熊出没旗舰店", "电影科技大揭秘"): "往东南走",
        ("方特城堡", "电影科技大揭秘"): "往东走",
        ("方特城堡", "大摆锤"): "往南走",

        ("游客服务中心", "售票处"): "往西走",
        ("游客服务中心", "代步车"): "往西南走",
        ("游客服务中心", "熊出没折扣店"): "往东走",
        ("游客服务中心", "大摆锤"): "往东南走",
        ("售票处", "寄存室"): "往东北走",
        ("寄存室", "熊出没旗舰店"): "往东南走",
        ("寄存室", "聊斋"): "往东走",

        ("熊出没折扣店", "游客服务中心"): "往西走",
        ("熊出没折扣店", "方特城堡"): "往东南走",
        ("熊出没折扣店", "熊出没旗舰店"): "往东走",
        ("电影科技大揭秘", "聊斋"): "往北走",
        ("电影科技大揭秘", "海螺湾"): "往东走",

        ("聊斋", "魔法城堡"): "往东北走",
        ("许愿树", "魔法城堡"): "往北走",
        ("许愿树", "海螺湾"): "往东南走",
        ("海螺湾", "梦幻广场"): "往东走",
        ("梦幻广场", "唐古拉雪山"): "往东南走",
        ("梦幻广场", "逃出恐龙岛"): "往东北走",
        ("唐古拉雪山", "逃出恐龙岛"): "往北走",
        ("唐古拉雪山", "东关削面王"): "往东走",
        ("唐古拉雪山", "生命之光"): "往东南走",

        ("生命之光", "宇宙博览会"): "往东走",
        ("宇宙博览会", "飞越极限"): "往东走",
        ("宇宙博览会", "双层转马"): "往南走",
        ("飞越极限", "高空飞翔"): "往南走",
        ("飞越极限", "华夏五千年"): "往东南走",
        ("高空飞翔", "华夏五千年"): "往东走",
        ("高空飞翔", "双层转马"): "往西走",

        ("双层转马", "临水餐厅"): "往南走",
        ("双层转马", "吉祥馄饨"): "往西南走",
        ("临水餐厅", "火流星"): "往西走",
        ("火流星", "吉祥馄饨"): "往西北走",
        ("火流星", "飓风飞椅"): "往西南走",
        ("吉祥馄饨", "熊出没脱口秀"): "往南走",
        ("熊出没脱口秀", "熊出没历险记"): "往南走",

        ("熊出没历险记", "恐龙飞车"): "往东走",
        ("熊出没历险记", "德克士"): "往西南走",
        ("恐龙飞车", "超级救火队"): "往东南走",
        ("恐龙飞车", "熊熊海盗船"): "往南走",
        ("熊熊海盗船", "海马骑兵"): "往东走",
        ("熊熊海盗船", "小奇兵"): "往西南走",
        ("超级救火队", "海马骑兵"): "往南走",
        ("海马骑兵", "欢乐滑车"): "往南走",
        ("欢乐滑车", "欢乐袋鼠"): "往西走",
        ("欢乐袋鼠", "嘟嘟小车"): "往西走",
        ("嘟嘟小车", "冰雪列车"): "往西南走",
        ("冰雪列车", "小奇兵"): "往北走",
        ("小奇兵", "恐龙飞车"): "往东北走",
        ("德克士", "童梦天地"): "往西北走",
        ("童梦天地", "疯狂成语"): "往南走",
        ("童梦天地", "飓风飞椅"): "往西走",
        ("疯狂成语", "波浪翻滚"): "往西南走",
        ("疯狂成语", "海盗船"): "往西走",

        ("飓风飞椅", "大摆锤"): "往西走",
        ("飓风飞椅", "空中飞舞"): "往南走",
        ("空中飞舞", "大摆锤"): "往西北走",
        ("空中飞舞", "海盗船"): "往南走",
        ("海盗船", "波浪翻滚"): "往南走",
    }

    def __init__(self, current_location=None, poi_registry_path=None):
        self.graph, self.edge_directions = self._build_graph()
        self.current_location = current_location or self.DEFAULT_START
        self._poi_registry_path = poi_registry_path
        self._poi_registry = None

    def _get_poi_registry(self):
        if self._poi_registry is None:
            path = self._poi_registry_path or os.path.join(
                os.path.dirname(__file__), "data", "poi_registry.json"
            )
            if os.path.isfile(path):
                self._poi_registry = load_poi_registry(path)
            else:
                self._poi_registry = {}
        return self._poi_registry

    # 设施类：不走路网，只在 2D 地图上高亮全部同类型点
    FACILITY_ALIASES = {
        "toilet": ["厕所", "卫生间", "洗手间", "公厕", "WC", "wc"],
    }

    def answer(self, speech_text):
        """返回地图问路JSON。"""
        facility = self.match_facility(speech_text)
        if facility == "toilet":
            return self._response(
                "想上厕所呀！园区里有好几处卫生间，俺已经在 2D 地图上用闪烁标记帮你标出来了，"
                "找离你近的黄色厕所图标就行。",
                ["左转指左"],
                "smile",
                found=True,
                highlight_category="toilet",
            )

        destination = self.match_place(speech_text)
        if not destination:
            return self._response(
                "这个地方俺还没找着，你可以问问海螺湾、飞越极限、熊出没历险记，"
                "或者说「厕所」让俺在地图上标出卫生间。",
                ["挠头歪身"],
                "confused",
                found=False,
            )

        if destination == self.current_location:
            return self._response(
                f"{destination}呀？你现在就在{self.current_location}附近，不用绕路啦！",
                ["双手欢呼"],
                "smile",
                destination=destination,
                path=[self.current_location],
                found=True,
            )

        path, distance = self.shortest_path(self.current_location, destination)
        if not path:
            return self._response(
                f"去{destination}呀？俺这张地图上路线还没连好，暂时没法给你指清楚。",
                ["挠头歪身"],
                "confused",
                destination=destination,
                found=False,
            )

        route_text = self._format_route(path, distance)
        return self._response(
            f"去{destination}呀！咱们现在在{self.current_location}。{route_text}",
            ["左转指左"],
            "smile",
            destination=destination,
            path=path,
            found=True,
        )

    def match_facility(self, speech_text):
        """匹配厕所等设施（优先于普通景点）。"""
        text = (speech_text or "").strip()
        if not text:
            return None
        candidates = []
        for facility_id, aliases in self.FACILITY_ALIASES.items():
            for alias in aliases:
                candidates.append((alias, facility_id))
        candidates.sort(key=lambda item: len(item[0]), reverse=True)
        for alias, facility_id in candidates:
            if alias in text:
                return facility_id
        return None

    def match_place(self, speech_text):
        """用关键词和别名匹配地点。"""
        text = (speech_text or "").strip()
        if not text:
            return None

        candidates = []
        for place_name, aliases in self.ALIASES.items():
            for alias in aliases:
                candidates.append((alias, place_name))

        candidates.sort(key=lambda item: len(item[0]), reverse=True)
        for alias, place_name in candidates:
            if alias in text:
                return place_name
        return None

    def shortest_path(self, start, destination):
        """Dijkstra 带权最短路。"""
        if start not in self.graph or destination not in self.graph:
            return None, None

        distances = {start: 0}
        previous = {}
        queue = [(0, start)]
        visited = set()

        while queue:
            current_distance, node = heapq.heappop(queue)
            if node in visited:
                continue
            visited.add(node)

            if node == destination:
                break

            for neighbor, weight in self.graph[node]:
                new_distance = current_distance + weight
                if new_distance < distances.get(neighbor, float("inf")):
                    distances[neighbor] = new_distance
                    previous[neighbor] = node
                    heapq.heappush(queue, (new_distance, neighbor))

        if destination not in distances:
            return None, None

        path = [destination]
        while path[-1] != start:
            path.append(previous[path[-1]])
        path.reverse()
        return path, distances[destination]

    def _build_graph(self):
        graph = {place: [] for place in self.ALIASES}
        edge_directions = {}
        best_edges = {}

        for start, end, weight in self.EDGES:
            if start not in graph or end not in graph:
                continue
            self._remember_edge(best_edges, start, end, weight)
            self._remember_edge(best_edges, end, start, weight)

        for (start, end), weight in best_edges.items():
            graph[start].append((end, weight))
            edge_directions[(start, end)] = self._edge_direction(start, end)

        return graph, edge_directions

    @staticmethod
    def _remember_edge(best_edges, start, end, weight):
        """重复边只保留权重更小的一条，避免来回都写时影响最短路。"""
        key = (start, end)
        if key not in best_edges or weight < best_edges[key]:
            best_edges[key] = weight

    @staticmethod
    def _edge_direction(start, end):
        direction = MapGuide.EDGE_DIRECTIONS.get((start, end))
        if direction:
            return direction

        reverse_direction = MapGuide.EDGE_DIRECTIONS.get((end, start))
        if reverse_direction:
            return MapGuide._reverse_direction(reverse_direction)

        return f"往{end}那边走"

    @staticmethod
    def _reverse_direction(direction):
        return direction.translate(str.maketrans("东西南北", "西东北南"))

    def _direction_between(self, start, end):
        return self.edge_directions.get((start, end), f"朝{end}方向走")

    def _format_route(self, path, distance):
        if len(path) <= 1:
            return "就在这儿。"

        first_stop = path[1]
        first_direction = self._direction_between(path[0], first_stop)
        destination = path[-1]
        direction_text = f"从{path[0]}到{first_stop}，需要{first_direction}。"

        if len(path) == 2:
            return f"直接到{destination}就可以啦。{direction_text}"

        middle_stops = path[2:-1]
        if middle_stops:
            middle_text = "，接着我们要经过" + "、".join(middle_stops)
        else:
            middle_text = ""

        return (
            f"先到{first_stop}{middle_text}，最后就能到达{destination}。"
            f"{direction_text}"
        )

    def _response(
        self,
        speech,
        actions,
        emotion,
        *,
        destination=None,
        path=None,
        found=None,
        highlight_category=None,
        highlight_names=None,
    ):
        payload = {
            "interaction_type": "map_query",
            "speech": speech,
            "motion_type": "sequential",
            "actions": actions,
            "motion_description": None,
            "emotion": emotion,
        }
        if destination is not None:
            payload["destination"] = destination
        if path is not None:
            payload["path"] = path
        if found is not None:
            payload["found"] = found
        if highlight_category:
            payload["highlight_category"] = highlight_category
        if highlight_names:
            payload["highlight_names"] = list(highlight_names)
        if path and found:
            registry = self._get_poi_registry()
            if registry:
                world_points = registry_path_world(registry, path)
                if world_points:
                    payload["path_world"] = world_points
                dest_world = get_place_world(registry, destination) if destination else None
                if dest_world:
                    payload["destination_world"] = dest_world
        return payload
