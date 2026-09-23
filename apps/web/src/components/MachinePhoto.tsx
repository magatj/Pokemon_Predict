export function MachinePhoto() {
  return (
    <figure className="machine-photo">
      <img
        src={`${import.meta.env.BASE_URL}images/vending-machine.jpg`}
        alt="An example Pokémon Center vending machine with a touchscreen and Poké Ball sign"
      />
      <figcaption>
        <span>Pokémon Center</span>
        <strong>Your next find starts here.</strong>
        <a
          href="https://www.linkedin.com/posts/rodneymason_gotta-catch-em-all-at-the-grocery-store-activity-7434065093870452736-BaZh"
          target="_blank" rel="noreferrer noopener"
        >Representative machine photo · Rod Mason</a>
      </figcaption>
    </figure>
  );
}
