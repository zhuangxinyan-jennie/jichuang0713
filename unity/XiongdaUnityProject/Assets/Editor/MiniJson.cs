using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace XiongdaImporter
{
    internal static class MiniJson
    {
        public static object Deserialize(string json)
        {
            if (json == null)
            {
                return null;
            }

            return Parser.Parse(json);
        }

        private sealed class Parser : IDisposable
        {
            private const string WordBreak = "{}[],:\"";

            private readonly StringReader json;

            private Parser(string jsonString)
            {
                json = new StringReader(jsonString);
            }

            public static object Parse(string jsonString)
            {
                using (var parser = new Parser(jsonString))
                {
                    return parser.ParseValue();
                }
            }

            public void Dispose()
            {
                json.Dispose();
            }

            private IDictionary<string, object> ParseObject()
            {
                var table = new Dictionary<string, object>();
                json.Read();

                while (true)
                {
                    switch (NextToken)
                    {
                        case Token.None:
                            return null;
                        case Token.CurlyClose:
                            json.Read();
                            return table;
                        default:
                            var name = ParseString();
                            if (name == null)
                            {
                                return null;
                            }

                            if (NextToken != Token.Colon)
                            {
                                return null;
                            }

                            json.Read();
                            table[name] = ParseValue();
                            break;
                    }
                }
            }

            private IList<object> ParseArray()
            {
                var array = new List<object>();
                json.Read();

                var parsing = true;
                while (parsing)
                {
                    var token = NextToken;
                    switch (token)
                    {
                        case Token.None:
                            return null;
                        case Token.SquaredClose:
                            json.Read();
                            parsing = false;
                            break;
                        default:
                            array.Add(ParseByToken(token));
                            break;
                    }
                }

                return array;
            }

            private object ParseValue()
            {
                return ParseByToken(NextToken);
            }

            private object ParseByToken(Token token)
            {
                switch (token)
                {
                    case Token.String:
                        return ParseString();
                    case Token.Number:
                        return ParseNumber();
                    case Token.CurlyOpen:
                        return ParseObject();
                    case Token.SquaredOpen:
                        return ParseArray();
                    case Token.True:
                        return true;
                    case Token.False:
                        return false;
                    case Token.Null:
                        return null;
                    default:
                        return null;
                }
            }

            private string ParseString()
            {
                var s = new StringBuilder();
                json.Read();

                var parsing = true;
                while (parsing)
                {
                    if (json.Peek() == -1)
                    {
                        break;
                    }

                    var c = NextChar;
                    switch (c)
                    {
                        case '"':
                            parsing = false;
                            break;
                        case '\\':
                            if (json.Peek() == -1)
                            {
                                parsing = false;
                                break;
                            }

                            c = NextChar;
                            switch (c)
                            {
                                case '"':
                                case '\\':
                                case '/':
                                    s.Append(c);
                                    break;
                                case 'b':
                                    s.Append('\b');
                                    break;
                                case 'f':
                                    s.Append('\f');
                                    break;
                                case 'n':
                                    s.Append('\n');
                                    break;
                                case 'r':
                                    s.Append('\r');
                                    break;
                                case 't':
                                    s.Append('\t');
                                    break;
                                case 'u':
                                {
                                    var hex = new char[4];
                                    for (var i = 0; i < 4; i++)
                                    {
                                        hex[i] = NextChar;
                                    }

                                    s.Append((char)Convert.ToInt32(new string(hex), 16));
                                    break;
                                }
                            }

                            break;
                        default:
                            s.Append(c);
                            break;
                    }
                }

                return s.ToString();
            }

            private object ParseNumber()
            {
                var number = NextWord;
                if (number.IndexOf('.') == -1 && number.IndexOf('e') == -1 && number.IndexOf('E') == -1)
                {
                    if (long.TryParse(number, out var parsedInt))
                    {
                        return parsedInt;
                    }
                }

                if (double.TryParse(number, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out var parsedDouble))
                {
                    return parsedDouble;
                }

                return 0d;
            }

            private void EatWhitespace()
            {
                while (char.IsWhiteSpace(PeekChar))
                {
                    json.Read();
                    if (json.Peek() == -1)
                    {
                        break;
                    }
                }
            }

            private char PeekChar
            {
                get
                {
                    var peek = json.Peek();
                    return peek == -1 ? '\0' : Convert.ToChar(peek);
                }
            }

            private char NextChar => Convert.ToChar(json.Read());

            private string NextWord
            {
                get
                {
                    var word = new StringBuilder();
                    while (!IsWordBreak(PeekChar))
                    {
                        word.Append(NextChar);
                        if (json.Peek() == -1)
                        {
                            break;
                        }
                    }

                    return word.ToString();
                }
            }

            private Token NextToken
            {
                get
                {
                    EatWhitespace();
                    if (json.Peek() == -1)
                    {
                        return Token.None;
                    }

                    switch (PeekChar)
                    {
                        case '{':
                            return Token.CurlyOpen;
                        case '}':
                            return Token.CurlyClose;
                        case '[':
                            return Token.SquaredOpen;
                        case ']':
                            return Token.SquaredClose;
                        case ',':
                            json.Read();
                            return NextToken;
                        case '"':
                            return Token.String;
                        case ':':
                            return Token.Colon;
                        case '0':
                        case '1':
                        case '2':
                        case '3':
                        case '4':
                        case '5':
                        case '6':
                        case '7':
                        case '8':
                        case '9':
                        case '-':
                            return Token.Number;
                    }

                    switch (NextWord)
                    {
                        case "false":
                            return Token.False;
                        case "true":
                            return Token.True;
                        case "null":
                            return Token.Null;
                    }

                    return Token.None;
                }
            }

            private static bool IsWordBreak(char c)
            {
                return char.IsWhiteSpace(c) || WordBreak.IndexOf(c) != -1;
            }
        }

        private enum Token
        {
            None,
            CurlyOpen,
            CurlyClose,
            SquaredOpen,
            SquaredClose,
            Colon,
            String,
            Number,
            True,
            False,
            Null
        }
    }
}
