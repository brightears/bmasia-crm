export interface DailyQuote {
  text: string;
  author: string;
}

const quotes: DailyQuote[] = [
  // Music industry wisdom
  { text: "Music is the shorthand of emotion.", author: "Leo Tolstoy" },
  { text: "Where words fail, music speaks.", author: "Hans Christian Andersen" },
  { text: "One good thing about music, when it hits you, you feel no pain.", author: "Bob Marley" },
  { text: "Without music, life would be a mistake.", author: "Friedrich Nietzsche" },
  { text: "Music gives a soul to the universe, wings to the mind, flight to the imagination.", author: "Plato" },
  { text: "If music be the food of love, play on.", author: "William Shakespeare" },
  { text: "Music is the universal language of mankind.", author: "Longfellow" },
  { text: "After silence, that which comes nearest to expressing the inexpressible is music.", author: "Aldous Huxley" },
  { text: "Music can change the world because it can change people.", author: "Bono" },
  { text: "I think music in itself is healing.", author: "Billy Joel" },
  { text: "The earth has music for those who listen.", author: "Shakespeare" },
  { text: "Music is a world within itself, with a language we all understand.", author: "Stevie Wonder" },
  { text: "Music is moonlight in the gloomy night of life.", author: "Jean Paul Richter" },
  { text: "Life is like a beautiful melody, only the lyrics are messed up.", author: "Hans Christian Andersen" },
  { text: "Where words leave off, music begins.", author: "Heinrich Heine" },
  { text: "Music expresses that which cannot be said and on which it is impossible to be silent.", author: "Victor Hugo" },

  // Fun & music humor
  { text: "I don't make music for eyes. I make music for ears.", author: "Adele" },
  { text: "People haven't always been there for me, but music always has.", author: "Taylor Swift" },
  { text: "Music is the wine that fills the cup of silence.", author: "Robert Fripp" },
  { text: "You can't copy anybody and end up with anything. If you copy, it means you're working without any real feeling.", author: "Billie Holiday" },
  { text: "If you cannot teach me to fly, teach me to sing.", author: "J.M. Barrie" },
  { text: "Music doesn't lie. If there is something to be changed in this world, then it can only happen through music.", author: "Jimi Hendrix" },
  { text: "To stop the flow of music would be like the stopping of time itself.", author: "Aaron Copland" },
  { text: "Music is the strongest form of magic.", author: "Marilyn Manson" },
  { text: "A painter paints pictures on canvas. But musicians paint their pictures on silence.", author: "Leopold Stokowski" },
  { text: "Music produces a kind of pleasure which human nature cannot do without.", author: "Confucius" },
  { text: "Without music, life is a journey through a desert.", author: "Pat Conroy" },
  { text: "Music is the soundtrack of your life.", author: "Dick Clark" },
  { text: "The only truth is music.", author: "Jack Kerouac" },
  { text: "Music is the art which is most nigh to tears and memory.", author: "Oscar Wilde" },

  // Business meets music
  { text: "And in the end, the love you take is equal to the love you make.", author: "The Beatles" },
  { text: "Every song has a memory; every song has the ability to make or break your heart.", author: "Frank Sinatra" },
  { text: "Music is like a dream. One that I cannot hear.", author: "Ludwig van Beethoven" },
  { text: "A great song should lift your heart, warm the soul, and make you feel good.", author: "Colbie Caillat" },
  { text: "Music washes away from the soul the dust of everyday life.", author: "Berthold Auerbach" },
  { text: "When you make music or write or create, it's really your job to have mind-blowing, irresponsible, condomless sex with whatever idea it is you're writing about.", author: "Lady Gaga" },
  { text: "Music, once admitted to the soul, becomes a sort of spirit, and never dies.", author: "Edward Bulwer-Lytton" },
  { text: "If I were not a physicist, I would probably be a musician.", author: "Albert Einstein" },
  { text: "I was born with music inside me. Music was one of my parts.", author: "Ray Charles" },
  { text: "Music is enough for a lifetime, but a lifetime is not enough for music.", author: "Sergei Rachmaninoff" },
];

/**
 * Returns a random quote on each page load.
 */
export const getDailyQuote = (): DailyQuote => {
  return quotes[Math.floor(Math.random() * quotes.length)];
};

export default quotes;
