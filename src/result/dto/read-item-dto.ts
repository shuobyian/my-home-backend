export interface ReadResultDto {
  id: number;
  name: string;
  level: number;
  craftingPrice: number;
  basic: {
    name: string;
    count: number;
    price: number;
  }[];
  totalPrice: number;
}
