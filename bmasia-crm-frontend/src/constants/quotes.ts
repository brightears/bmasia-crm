export interface DailyQuote {
  text: string;
  author: string;
}

const quotes: DailyQuote[] = [
  // Music & Creativity
  { text: "Music is the shorthand of emotion.", author: "Leo Tolstoy" },
  { text: "Where words fail, music speaks.", author: "Hans Christian Andersen" },
  { text: "One good thing about music, when it hits you, you feel no pain.", author: "Bob Marley" },
  { text: "Music expresses that which cannot be said and on which it is impossible to be silent.", author: "Victor Hugo" },
  { text: "Without music, life would be a mistake.", author: "Friedrich Nietzsche" },
  { text: "Music is the universal language of mankind.", author: "Henry Wadsworth Longfellow" },
  { text: "Music gives a soul to the universe, wings to the mind, flight to the imagination.", author: "Plato" },
  { text: "Life is like a beautiful melody, only the lyrics are messed up.", author: "Hans Christian Andersen" },
  { text: "Music is the strongest form of magic.", author: "Marilyn Manson" },
  { text: "After silence, that which comes nearest to expressing the inexpressible is music.", author: "Aldous Huxley" },
  { text: "Music is a world within itself, with a language we all understand.", author: "Stevie Wonder" },
  { text: "Where words leave off, music begins.", author: "Heinrich Heine" },
  { text: "Music is the soundtrack of your life.", author: "Dick Clark" },
  { text: "The only truth is music.", author: "Jack Kerouac" },
  { text: "Music can change the world because it can change people.", author: "Bono" },
  { text: "Music is the art which is most nigh to tears and memory.", author: "Oscar Wilde" },
  { text: "If music be the food of love, play on.", author: "William Shakespeare" },
  { text: "I think music in itself is healing.", author: "Billy Joel" },
  { text: "Music is what feelings sound like.", author: "Anonymous" },
  { text: "Every song has a memory; every song has the ability to make or break your heart.", author: "Frank Sinatra" },
  { text: "Music is moonlight in the gloomy night of life.", author: "Jean Paul Richter" },
  { text: "A great song should lift your heart, warm the soul, and make you feel good.", author: "Colbie Caillat" },
  { text: "Music is like a dream. One that I cannot hear.", author: "Ludwig van Beethoven" },
  { text: "To produce music is also in a sense to produce children.", author: "Friedrich Nietzsche" },
  { text: "The earth has music for those who listen.", author: "William Shakespeare" },

  // Business & Motivation
  { text: "The best way to predict the future is to create it.", author: "Peter Drucker" },
  { text: "Your work is going to fill a large part of your life. Do what you believe is great work.", author: "Steve Jobs" },
  { text: "Success is not final, failure is not fatal: it is the courage to continue that counts.", author: "Winston Churchill" },
  { text: "The only way to do great work is to love what you do.", author: "Steve Jobs" },
  { text: "It always seems impossible until it's done.", author: "Nelson Mandela" },
  { text: "Excellence is not a destination but a continuously expanding process.", author: "Deming" },
  { text: "Innovation distinguishes between a leader and a follower.", author: "Steve Jobs" },
  { text: "The secret of getting ahead is getting started.", author: "Mark Twain" },
  { text: "What you do today can improve all your tomorrows.", author: "Ralph Marston" },
  { text: "Don't count the days, make the days count.", author: "Muhammad Ali" },
  { text: "Great things in business are never done by one person. They're done by a team.", author: "Steve Jobs" },
  { text: "The way to get started is to quit talking and begin doing.", author: "Walt Disney" },
  { text: "Opportunities don't happen. You create them.", author: "Chris Grosser" },
  { text: "Your most unhappy customers are your greatest source of learning.", author: "Bill Gates" },
  { text: "Stay hungry, stay foolish.", author: "Steve Jobs" },
  { text: "In the middle of difficulty lies opportunity.", author: "Albert Einstein" },
  { text: "Quality is not an act, it is a habit.", author: "Aristotle" },
  { text: "The customer's perception is your reality.", author: "Kate Zabriskie" },
  { text: "Do what you can, with what you have, where you are.", author: "Theodore Roosevelt" },
  { text: "Be the change that you wish to see in the world.", author: "Mahatma Gandhi" },

  // Thai & Asian Wisdom
  { text: "A journey of a thousand miles begins with a single step.", author: "Lao Tzu" },
  { text: "The bamboo that bends is stronger than the oak that resists.", author: "Japanese Proverb" },
  { text: "Fall seven times, stand up eight.", author: "Japanese Proverb" },
  { text: "Patience is the companion of wisdom.", author: "Saint Augustine" },
  { text: "When the winds of change blow, some build walls while others build windmills.", author: "Chinese Proverb" },
  { text: "The best time to plant a tree was 20 years ago. The second best time is now.", author: "Chinese Proverb" },
  { text: "Do not dwell in the past, do not dream of the future, concentrate on the present moment.", author: "Buddha" },
  { text: "Peace comes from within. Do not seek it without.", author: "Buddha" },
  { text: "In a gentle way, you can shake the world.", author: "Mahatma Gandhi" },
  { text: "Still waters run deep.", author: "Thai Proverb" },

  // Seasonal & Fun
  { text: "Life is what happens when you're busy making other plans.", author: "John Lennon" },
  { text: "And in the end, the love you take is equal to the love you make.", author: "The Beatles" },
  { text: "Every day is a new beginning. Take a deep breath, smile, and start again.", author: "Anonymous" },
  { text: "The purpose of our lives is to be happy.", author: "Dalai Lama" },
  { text: "Keep your face always toward the sunshine, and shadows will fall behind you.", author: "Walt Whitman" },
];

/**
 * Returns the same quote for everyone on the same day.
 * Changes at midnight local time.
 */
export const getDailyQuote = (): DailyQuote => {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const dayOfYear = Math.floor((now.getTime() - start.getTime()) / 86400000);
  return quotes[dayOfYear % quotes.length];
};

/**
 * Returns a seasonal icon based on the current month.
 * Reflects Bangkok's tropical seasons and BMAsia's music focus.
 */
export const getSeasonalIcon = (): string => {
  const month = new Date().getMonth(); // 0-indexed
  if (month === 11 || month <= 1) return '\u2744\uFE0F'; // ❄️ Dec-Feb (Cool season)
  if (month >= 2 && month <= 4) return '\uD83C\uDF38';   // 🌸 Mar-May (Spring/Songkran)
  if (month >= 5 && month <= 7) return '\u2600\uFE0F';   // ☀️ Jun-Aug (Summer)
  return '\uD83C\uDF42';                                   // 🍂 Sep-Nov (Autumn/Festivals)
};

export default quotes;
