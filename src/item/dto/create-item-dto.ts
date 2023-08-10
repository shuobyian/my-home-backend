export class CreateItemDto {
  name: string;
  level: number;
  craftingPrice: number;
  materials: {
    name: string;
    base: boolean;
    count: number;
  }[];
}
