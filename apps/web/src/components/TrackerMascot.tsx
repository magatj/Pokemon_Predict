/** A small brand accent, kept out of the reading order. */
export function TrackerMascot() {
  return (
    <div className="tracker-mascot" aria-hidden="true">
      <img src={`${import.meta.env.BASE_URL}images/pikachu.png`} alt="" width="475" height="475" />
      <p>Catch the<br />next drop!</p>
    </div>
  );
}
