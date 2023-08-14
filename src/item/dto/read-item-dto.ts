import { CreateItemDto } from 'src/item/dto/create-item-dto';

export class ReadItemDto extends CreateItemDto {
  id: number;
}

export class RawItemDto {
  name: string;
  level: number;
  craftingPrice: number;
  material1: string;
  base1: number;
  count1: number;
  material2: string;
  base2: number;
  count2: number;
  material3: string;
  base3: number;
  count3: number;
  material4: string;
  base4: number;
  count4: number;
  material5: string;
  base5: number;
  count5: number;
}
