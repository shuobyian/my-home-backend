import { Column, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('result', { schema: 'public' })
export class Result {
  @PrimaryGeneratedColumn({ type: 'integer', name: 'id' })
  id: number;

  @Column('varchar', { unique: true, name: 'name' })
  name: string;

  @Column('integer', { name: 'level' })
  level: number;

  @Column('integer', { name: 'craftingPrice' })
  craftingPrice: number;

  @Column('string', { name: 'basic' })
  basic: string;

  @Column('string', { name: 'counts' })
  counts: string;

  @Column('string', { name: 'prices' })
  prices: string;

  @Column('integer', { name: 'totalPrice' })
  totalPrice: number;
}
