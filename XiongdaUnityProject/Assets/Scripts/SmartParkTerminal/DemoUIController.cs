using UnityEngine;
using UnityEngine.UI;

namespace SmartParkTerminal
{
    /// <summary>触摸屏按钮 → 构造指令（模拟 310B JSON）</summary>
    public sealed class DemoUIController : MonoBehaviour
    {
        [SerializeField]
        private Transform characterButtonsRoot;

        [SerializeField]
        private Transform navButtonsRoot;

        [SerializeField]
        private Transform mapButtonsRoot;

        private SmartTerminalController _terminal;

        private void Awake()
        {
            WireCharacterButtons(characterButtonsRoot);
            WireCharacterButtons(navButtonsRoot);
            WireMapButtons(mapButtonsRoot);
        }

        public void BindTerminal(SmartTerminalController terminal)
        {
            _terminal = terminal;
        }

        private void WireCharacterButtons(Transform root)
        {
            if (root == null)
            {
                return;
            }

            foreach (Button b in root.GetComponentsInChildren<Button>(true))
            {
                if (b == null)
                {
                    continue;
                }

                string n = b.gameObject.name;
                if (n == "BtnIdle")
                {
                    b.onClick.AddListener(PlayIdle);
                }
                else if (n == "BtnWave")
                {
                    b.onClick.AddListener(PlayWave);
                }
                else if (n == "BtnLaugh")
                {
                    b.onClick.AddListener(PlayLaugh);
                }
                else if (n == "BtnNod")
                {
                    b.onClick.AddListener(PlayNod);
                }
                else if (n == "BtnRandom")
                {
                    b.onClick.AddListener(SimulateRandomInteraction);
                }
                else if (n == "BtnModeSelect")
                {
                    b.onClick.AddListener(PlayModeSelectIntro);
                }
                else if (n == "BtnStoryWake")
                {
                    b.onClick.AddListener(PlayStoryIntroWakeChoice);
                }
                else if (n == "BtnHoney")
                {
                    b.onClick.AddListener(PlayStoryWakeYesHoneyTrick);
                }
                else if (n == "BtnCheerYes")
                {
                    b.onClick.AddListener(PlayStoryWakeYesCheerYes);
                }
                else if (n == "BtnCheerNo")
                {
                    b.onClick.AddListener(PlayStoryWakeYesCheerNo);
                }
                else if (n == "BtnDream")
                {
                    b.onClick.AddListener(PlayStoryWakeNoDreamWakeup);
                }
                else if (n == "BtnFightYes")
                {
                    b.onClick.AddListener(PlayStoryWakeNoFightYes);
                }
                else if (n == "BtnFightNo")
                {
                    b.onClick.AddListener(PlayStoryWakeNoFightNo);
                }
                else if (n == "BtnFinale")
                {
                    b.onClick.AddListener(PlayStoryFinaleReturn);
                }
                else if (n == "BtnStoryYesBranch")
                {
                    b.onClick.AddListener(SimulateFullStoryBranchYes);
                }
                else if (n == "BtnStoryNoBranch")
                {
                    b.onClick.AddListener(SimulateFullStoryBranchNo);
                }
                else if (n == "BtnPageCharacter")
                {
                    b.onClick.AddListener(UiGoCharacter);
                }
                else if (n == "BtnPageMap")
                {
                    b.onClick.AddListener(UiGoMap);
                }
                else if (n == "BtnPageRecommend")
                {
                    b.onClick.AddListener(UiGoRecommend);
                }
                else if (n == "BtnPageSystem")
                {
                    b.onClick.AddListener(UiGoSystem);
                }
            }
        }

        private void WireMapButtons(Transform root)
        {
            if (root == null)
            {
                return;
            }

            foreach (Button b in root.GetComponentsInChildren<Button>(true))
            {
                if (b == null)
                {
                    continue;
                }

                string n = b.gameObject.name;
                if (n == "BtnMapCarousel")
                {
                    b.onClick.AddListener(MapQueryCarousel);
                }
                else if (n == "BtnMapCoaster")
                {
                    b.onClick.AddListener(MapQueryCoaster);
                }
                else if (n == "BtnMapFood")
                {
                    b.onClick.AddListener(MapQueryFood);
                }
                else if (n == "BtnMapRestroom")
                {
                    b.onClick.AddListener(MapQueryRestroom);
                }
                else if (n == "BtnMapExit")
                {
                    b.onClick.AddListener(MapQueryExit);
                }
                else if (n == "BtnMapXiongda")
                {
                    b.onClick.AddListener(MapQueryXiongdaZone);
                }
            }
        }

        private void Post(TerminalCommand cmd)
        {
            if (_terminal == null)
            {
                _terminal = FindObjectOfType<SmartTerminalController>();
            }

            if (_terminal == null)
            {
                return;
            }

            _terminal.DispatchCommand(cmd, true);
        }

        public void PlayIdle()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "stand_idle_friendly",
                emotion = "smile"
            });
        }

        public void PlayWave()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "wave_right_hand",
                emotion = "smile"
            });
        }

        public void PlayLaugh()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "laugh",
                emotion = "happy"
            });
        }

        public void PlayNod()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "nod",
                emotion = "smile"
            });
        }

        public void PlayModeSelectIntro()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "mode_select_intro",
                emotion = "smile"
            });
        }

        public void PlayStoryIntroWakeChoice()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "story_intro_wake_choice",
                emotion = "smile"
            });
        }

        public void PlayStoryWakeYesHoneyTrick()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "story_wake_yes_honey_trick",
                emotion = "smile"
            });
        }

        public void PlayStoryWakeYesCheerYes()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "story_wake_yes_cheer_yes",
                emotion = "happy"
            });
        }

        public void PlayStoryWakeYesCheerNo()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "story_wake_yes_cheer_no",
                emotion = "smile"
            });
        }

        public void PlayStoryWakeNoDreamWakeup()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "story_wake_no_dream_wakeup",
                emotion = "smile"
            });
        }

        public void PlayStoryWakeNoFightYes()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "story_wake_no_fight_yes",
                emotion = "happy"
            });
        }

        public void PlayStoryWakeNoFightNo()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "story_wake_no_fight_no",
                emotion = "smile"
            });
        }

        public void PlayStoryFinaleReturn()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_id = "story_finale_return",
                emotion = "happy"
            });
        }

        public void SimulateRandomInteraction()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "random_interaction",
                speech = "嘿！你好呀！",
                motion_type = "layered",
                actions = new[] { "stand_idle_friendly", "wave_right_hand" },
                emotion = "smile"
            });
        }

        public void SimulateMapQueryCarousel()
        {
            MapQueryCarousel();
        }

        public void MapQueryCarousel()
        {
            Post(new TerminalCommand
            {
                module = "map_query",
                speech = "旋转木马在园区东侧，沿着主路往右走就能看到。",
                ui_action = "show_map",
                highlight_poi = "carousel",
                clip_id = "point_right",
                emotion = "smile"
            });
        }

        public void MapQueryCoaster()
        {
            Post(new TerminalCommand
            {
                module = "map_query",
                speech = "过山车在高架轨道区，顺着尖叫声就能找到！",
                ui_action = "show_map",
                highlight_poi = "roller_coaster",
                clip_id = "point_right",
                emotion = "smile"
            });
        }

        public void MapQueryFood()
        {
            Post(new TerminalCommand
            {
                module = "map_query",
                speech = "餐饮区在中央广场北边，累了可以去吃点东西。",
                ui_action = "show_map",
                highlight_poi = "food_area",
                clip_id = "point_left",
                emotion = "smile"
            });
        }

        public void MapQueryRestroom()
        {
            Post(new TerminalCommand
            {
                module = "map_query",
                speech = "卫生间在各主题区都有指示牌，俺帮你标出来啦。",
                ui_action = "show_map",
                highlight_poi = "restroom",
                clip_id = "point_right",
                emotion = "smile"
            });
        }

        public void MapQueryExit()
        {
            Post(new TerminalCommand
            {
                module = "map_query",
                speech = "出口在这边，跟着绿色疏散标识走就好。",
                ui_action = "show_map",
                highlight_poi = "exit",
                clip_id = "point_left",
                emotion = "smile"
            });
        }

        public void MapQueryXiongdaZone()
        {
            Post(new TerminalCommand
            {
                module = "map_query",
                speech = "熊大互动区就在这片舞台附近，欢迎来找俺玩！",
                ui_action = "show_map",
                highlight_poi = "xiongda_zone",
                clip_id = "talk_gesture_small",
                emotion = "smile"
            });
        }

        public void SimulateRecommendationTrain()
        {
            Post(new TerminalCommand
            {
                module = "recommendation",
                speech = "我推荐你先去森林小火车，排队时间比较短。",
                clip_id = "talk_gesture_small",
                emotion = "smile",
                recommendation = new RecommendationData
                {
                    name = "森林小火车",
                    reason = "路线轻松，适合休息",
                    queue_time = "5分钟",
                    target_group = "全年龄"
                }
            });
        }

        public void SimulateFullStoryBranchYes()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_ids = new[] { "story_wake_yes_cheer_yes", "story_finale_return" },
                speech = "太好啦！俺感觉现在浑身都是劲儿！",
                emotion = "happy"
            });
        }

        public void SimulateFullStoryBranchNo()
        {
            Post(new TerminalCommand
            {
                module = "character_interaction",
                interaction_type = "story_interaction",
                clip_ids = new[] { "story_wake_no_fight_no", "story_finale_return" },
                speech = "没关系，俺罩着你！",
                emotion = "smile"
            });
        }

        public void UiGoCharacter()
        {
            if (_terminal == null)
            {
                _terminal = FindObjectOfType<SmartTerminalController>();
            }

            _terminal.ShowCharacterPage();
        }

        public void UiGoMap()
        {
            if (_terminal == null)
            {
                _terminal = FindObjectOfType<SmartTerminalController>();
            }

            _terminal.ShowMapPage();
        }

        public void UiGoRecommend()
        {
            if (_terminal == null)
            {
                _terminal = FindObjectOfType<SmartTerminalController>();
            }

            _terminal.ShowRecommendationPage();
        }

        public void UiGoSystem()
        {
            if (_terminal == null)
            {
                _terminal = FindObjectOfType<SmartTerminalController>();
            }

            _terminal.ShowSystemPage();
        }
    }
}
